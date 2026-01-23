#!/usr/bin/env python3
import sys
import os
import json
from pathlib import Path

# Add parent directory to path to import db
sys.path.insert(0, str(Path(__file__).parent.parent))
from db import get_db

def seed_roles(db):
    """Seed roles table"""
    data_dir = Path(__file__).parent.parent / 'data'
    roles_file = data_dir / 'roles.json'
    
    if not roles_file.exists():
        print(f"Warning: {roles_file} not found. Run generate-data.py first.")
        return
    
    with open(roles_file, 'r', encoding='utf-8') as f:
        roles_data = json.load(f)
    
    cursor = db.cursor()
    for role in roles_data:
        cursor.execute('''
            INSERT OR REPLACE INTO roles (id, name, description, required_skills)
            VALUES (?, ?, ?, ?)
        ''', (
            role['id'],
            role['name'],
            role['description'],
            json.dumps(role['required_skills'])
        ))
    
    db.commit()
    print(f'Seeded {len(roles_data)} roles')


def seed_resources(db):
    """Seed resources table"""
    data_dir = Path(__file__).parent.parent / 'data'
    resources_file = data_dir / 'resources.json'
    
    if not resources_file.exists():
        print(f"Warning: {resources_file} not found. Run generate-data.py first.")
        return
    
    with open(resources_file, 'r', encoding='utf-8') as f:
        resources_data = json.load(f)
    
    cursor = db.cursor()
    for skill_group in resources_data:
        for resource in skill_group['resources']:
            cursor.execute('''
                INSERT OR REPLACE INTO resources (skill, title, url, type, level)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                skill_group['skill'],
                resource['title'],
                resource['url'],
                resource['type'],
                resource['level']
            ))
    
    db.commit()
    print('Seeded resources')


def seed_questions(db):
    """Seed questions table"""
    data_dir = Path(__file__).parent.parent / 'data'
    questions_file = data_dir / 'questions.json'
    
    if not questions_file.exists():
        print(f"Warning: {questions_file} not found. Run generate-data.py first.")
        return
    
    with open(questions_file, 'r', encoding='utf-8') as f:
        questions_data = json.load(f)
    
    cursor = db.cursor()
    for question in questions_data:
        cursor.execute('''
            INSERT OR REPLACE INTO questions (id, question, category, subcategory, answer_type, options, skill_mappings)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            question['id'],
            question['question'],
            question.get('category', 'Personality'),
            question.get('subcategory', 'General'),
            question.get('answer_type', 'Likert5'),
            question.get('options', ''),
            json.dumps(question['skill_mappings'])
        ))
    
    db.commit()
    print(f'Seeded {len(questions_data)} questions')


def main():
    """Main seeding function"""
    print('Starting database seeding...')
    db = get_db()
    try:
        seed_roles(db)
        seed_resources(db)
        seed_questions(db)
        print('Database seeding completed!')
    finally:
        db.close()


if __name__ == '__main__':
    main()
