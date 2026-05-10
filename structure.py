import pathlib

def generate_structure(root_dir, indent="", exclude=None):
    if exclude is None:
        exclude = {'.git', '__pycache__', 'venv', '.env', '.pytest_cache', 'alembic'}

    root = pathlib.Path(root_dir)
    
    # Sort to keep folders first, then files
    items = sorted(root.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
    
    for i, item in enumerate(items):
        if item.name in exclude:
            continue
            
        is_last = (i == len(items) - 1)
        connector = "└── " if is_last else "├── "
        
        print(f"{indent}{connector}{item.name}")
        
        if item.is_dir():
            # Add pipe for nested levels if not the last item
            next_indent = indent + ("    " if is_last else "│   ")
            generate_structure(item, next_indent, exclude)

if __name__ == "__main__":
    project_root = pathlib.Path(__file__).parent
    print(f"{project_root.name}/")
    generate_structure(project_root)