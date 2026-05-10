import http from "k6/http";
import { check, sleep } from "k6";
import { Rate, Trend } from "k6/metrics";

const BASE_URL = __ENV.BASE_URL || "http://127.0.0.1:8000";
const RUN_BOOKING = (__ENV.RUN_BOOKING || "false").toLowerCase() === "true";
const EVENT_ID = __ENV.EVENT_ID || "";
const SEAT_TYPE = __ENV.SEAT_TYPE || "VIP";
const BOOK_QTY = Number(__ENV.BOOK_QTY || 1);

const businessFailRate = new Rate("business_fail_rate");
const healthLatency = new Trend("health_latency_ms");
const listEventsLatency = new Trend("list_events_latency_ms");
const createEventLatency = new Trend("create_event_latency_ms");
const bookEventLatency = new Trend("book_event_latency_ms");

export const options = {
  scenarios: {
    health: {
      executor: "ramping-arrival-rate",
      startRate: 5,
      timeUnit: "1s",
      preAllocatedVUs: 20,
      maxVUs: 120,
      stages: [
        { target: 20, duration: "1m" },
        { target: 40, duration: "2m" },
        { target: 70, duration: "2m" },
        { target: 100, duration: "2m" }
      ],
      exec: "healthScenario"
    },
    list_events: {
      executor: "ramping-arrival-rate",
      startRate: 3,
      timeUnit: "1s",
      preAllocatedVUs: 15,
      maxVUs: 100,
      stages: [
        { target: 10, duration: "1m" },
        { target: 25, duration: "2m" },
        { target: 40, duration: "2m" },
        { target: 60, duration: "2m" }
      ],
      exec: "listEventsScenario"
    },
    create_event: {
      executor: "constant-arrival-rate",
      rate: 2,
      timeUnit: "1s",
      duration: "7m",
      preAllocatedVUs: 10,
      maxVUs: 40,
      exec: "createEventScenario"
    },
    booking: {
      executor: "constant-arrival-rate",
      rate: RUN_BOOKING ? 2 : 0,
      timeUnit: "1s",
      duration: "7m",
      preAllocatedVUs: 10,
      maxVUs: 40,
      exec: "bookEventScenario"
    }
  },
  thresholds: {
    http_req_failed: ["rate<0.02"],
    http_req_duration: ["p(95)<1200", "p(99)<2500"],
    health_latency_ms: ["p(95)<600"],
    list_events_latency_ms: ["p(95)<900"],
    create_event_latency_ms: ["p(95)<1500"],
    book_event_latency_ms: ["p(95)<2000"],
    business_fail_rate: ["rate<0.05"]
  }
};

function mark(result) {
  businessFailRate.add(!result);
}

export function healthScenario() {
  const res = http.get(`${BASE_URL}/health`, { tags: { endpoint: "health" } });
  healthLatency.add(res.timings.duration);
  const ok = check(res, { "health status 200": (r) => r.status === 200 });
  mark(ok);
  sleep(0.2);
}

export function listEventsScenario() {
  const res = http.get(`${BASE_URL}/events`, { tags: { endpoint: "events_list" } });
  listEventsLatency.add(res.timings.duration);
  const ok = check(res, {
    "list events status 200": (r) => r.status === 200,
    "list events is array": (r) => {
      try { return Array.isArray(r.json()); } catch (e) { return false; }
    }
  });
  mark(ok);
  sleep(0.3);
}

export function createEventScenario() {
  const ts = Date.now();
  const payload = JSON.stringify({
    title: `LoadTest Event ${ts}`,
    type: "LOADTEST",
    date_time: "2026-12-31T18:00:00",
    location: "Load Zone",
    seat_types: [
      { seat_type: "Standard", price: 1000, total_seats: 20 },
      { seat_type: "VIP", price: 2500, total_seats: 10 }
    ]
  });
  const res = http.post(`${BASE_URL}/events`, payload, {
    headers: { "Content-Type": "application/json" },
    tags: { endpoint: "events_create" }
  });
  createEventLatency.add(res.timings.duration);
  const ok = check(res, { "create event status 200": (r) => r.status === 200 });
  mark(ok);
  sleep(0.4);
}

export function bookEventScenario() {
  if (!RUN_BOOKING) return;
  if (!EVENT_ID) {
    businessFailRate.add(true);
    return;
  }

  const payload = JSON.stringify({ seat_type: SEAT_TYPE, seat_count: BOOK_QTY });
  const res = http.post(`${BASE_URL}/events/${EVENT_ID}/book`, payload, {
    headers: { "Content-Type": "application/json" },
    tags: { endpoint: "events_book" }
  });
  bookEventLatency.add(res.timings.duration);
  const ok = check(res, { "book event status 200/409": (r) => r.status === 200 || r.status === 409 });
  mark(ok);
  sleep(0.2);
}
