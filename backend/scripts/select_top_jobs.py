#!/usr/bin/env python3
"""
Select top 10 jobs for adaptive quiz system.
"""
import json
from pathlib import Path


def select_top_jobs():
    """
    Select top 10 jobs covering major career paths:
    - Frontend Developer
    - Backend Developer
    - Full Stack Developer
    - Data Scientist
    - ML Engineer
    - DevOps Engineer
    - UX Designer
    - Product Manager
    - QA Engineer
    - Software Architect
    """
    roles_file = Path(__file__).parent.parent / 'data' / 'roles.json'
    
    if not roles_file.exists():
        print(f"Error: {roles_file} not found")
        return None
    
    with open(roles_file, 'r') as f:
        all_roles = json.load(f)
    
    # Define top 10 job IDs
    top_10_ids = [
        'frontend',
        'backend',
        'fullstack',
        'data-scientist',
        'ml-engineer',
        'devops',
        'ux-designer',
        'product-manager',
        'qa',
        'architect'
    ]
    
    top_10_roles = [role for role in all_roles if role['id'] in top_10_ids]
    
    # Verify we got all 10
    if len(top_10_roles) != 10:
        missing = set(top_10_ids) - {role['id'] for role in top_10_roles}
        if missing:
            print(f"Warning: Missing jobs: {missing}")
    
    # Save to separate file
    output_file = Path(__file__).parent.parent / 'data' / 'top_10_jobs.json'
    with open(output_file, 'w') as f:
        json.dump(top_10_roles, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Selected {len(top_10_roles)} jobs")
    print(f"✓ Saved to {output_file}")
    
    for role in top_10_roles:
        print(f"  - {role['name']}")
    
    return top_10_roles


if __name__ == '__main__':
    select_top_jobs()
