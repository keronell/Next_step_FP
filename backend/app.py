from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import os
import json
import uuid
from db import get_db

load_dotenv()

app = Flask(__name__)
CORS(app)

PORT = int(os.getenv('PORT', 3001))


def compute_skill_vector(answers, db):
    """Compute skill vector from answers"""
    skill_vector = {}
    
    for answer in answers:
        cursor = db.execute(
            'SELECT skill_mappings, answer_type FROM questions WHERE id = ?',
            (answer['question_id'],)
        )
        question = cursor.fetchone()
        
        if not question:
            continue
        
        skill_mappings = json.loads(question['skill_mappings'])
        
        # For Likert5: map 1-5 to 0-4 scale
        normalized_value = 0
        if question['answer_type'] == 'Likert5':
            answer_value = float(answer['answer_value']) if answer['answer_value'] else 0
            normalized_value = (answer_value - 1) / 4  # Maps 1->0, 5->1
        elif question['answer_type'] == 'SingleChoice':
            # For single choice, if answered, give partial credit
            normalized_value = 0.5 if answer['answer_value'] and answer['answer_value'] != 'Not sure' else 0
        elif question['answer_type'] == 'MultiChoice':
            # For multi choice, count selections (comma-separated)
            selections = [v for v in answer['answer_value'].split(',') if v and v != 'Not sure'] if answer['answer_value'] else []
            normalized_value = min(len(selections) * 0.3, 1)  # Up to 1.0 for multiple selections
        elif question['answer_type'] == 'Numeric':
            # Normalize numeric (e.g., hours per week: 0-40 -> 0-1)
            answer_value = float(answer['answer_value']) if answer['answer_value'] else 0
            normalized_value = min(answer_value / 40, 1)
        
        for skill, weight in skill_mappings.items():
            if skill not in skill_vector:
                skill_vector[skill] = 0
            skill_vector[skill] += normalized_value * weight
    
    # Normalize to 0-5 scale
    for skill in skill_vector:
        skill_vector[skill] = min(5, max(0, skill_vector[skill]))
    
    return skill_vector


@app.route('/api/sessions', methods=['POST'])
def create_session():
    """Create a new session"""
    session_id = str(uuid.uuid4())
    db = get_db()
    db.execute('INSERT INTO sessions (id) VALUES (?)', (session_id,))
    db.commit()
    db.close()
    return jsonify({'session_id': session_id})


@app.route('/api/questions', methods=['GET'])
def get_questions():
    """Get all questions"""
    db = get_db()
    cursor = db.execute('''
        SELECT id, question, category, subcategory, answer_type, options 
        FROM questions 
        ORDER BY id
    ''')
    questions = [dict(row) for row in cursor.fetchall()]
    db.close()
    return jsonify(questions)


@app.route('/api/sessions/<session_id>/answers', methods=['POST'])
def submit_answer(session_id):
    """Submit an answer"""
    data = request.json
    question_id = data.get('question_id')
    answer_value = data.get('answer_value')
    
    db = get_db()
    db.execute('''
        INSERT INTO answers (session_id, question_id, answer_value)
        VALUES (?, ?, ?)
    ''', (session_id, question_id, answer_value))
    db.commit()
    db.close()
    return jsonify({'success': True})


@app.route('/api/sessions/<session_id>/compute', methods=['POST'])
def compute_results(session_id):
    """Compute results and get top 5 roles"""
    db = get_db()
    
    # Get all answers for this session
    cursor = db.execute('''
        SELECT a.question_id, a.answer_value
        FROM answers a
        WHERE a.session_id = ?
    ''', (session_id,))
    answers = [dict(row) for row in cursor.fetchall()]
    
    # Compute skill vector
    skill_vector = compute_skill_vector(answers, db)
    
    # Store skill vector
    db.execute(
        'UPDATE sessions SET skill_vector = ? WHERE id = ?',
        (json.dumps(skill_vector), session_id)
    )
    db.commit()
    
    # Get all roles
    cursor = db.execute('SELECT * FROM roles')
    roles = [dict(row) for row in cursor.fetchall()]
    
    # Score each role
    scored_roles = []
    for role in roles:
        required_skills = json.loads(role['required_skills'])
        score = 0
        total_weight = 0
        reasons = []
        
        for skill, required_level in required_skills.items():
            user_level = skill_vector.get(skill, 0)
            match = min(user_level / required_level, 1) if required_level > 0 else 0
            score += match * required_level
            total_weight += required_level
            
            if user_level < required_level:
                reasons.append({
                    'skill': skill,
                    'gap': required_level - user_level,
                    'message': f'Need {required_level - user_level:.1f} more in {skill}'
                })
        
        final_score = (score / total_weight * 100) if total_weight > 0 else 0
        
        role_dict = dict(role)
        role_dict['score'] = round(final_score)
        role_dict['reasons'] = reasons[:3]  # Top 3 gaps
        scored_roles.append(role_dict)
    
    # Sort by score and get top 5
    top5 = sorted(scored_roles, key=lambda x: x['score'], reverse=True)[:5]
    
    # Mark session as completed
    db.execute(
        'UPDATE sessions SET completed_at = CURRENT_TIMESTAMP WHERE id = ?',
        (session_id,)
    )
    db.commit()
    db.close()
    
    return jsonify({
        'skill_vector': skill_vector,
        'top_roles': top5
    })


@app.route('/api/sessions/<session_id>/roadmap', methods=['POST'])
def generate_roadmap(session_id):
    """Generate roadmap for a role"""
    data = request.json
    role_id = data.get('role_id')
    
    db = get_db()
    
    # Get user skill vector
    cursor = db.execute('SELECT skill_vector FROM sessions WHERE id = ?', (session_id,))
    session = cursor.fetchone()
    
    if not session or not session['skill_vector']:
        db.close()
        return jsonify({'error': 'Session not found or not completed'}), 400
    
    skill_vector = json.loads(session['skill_vector'])
    
    # Get role requirements
    cursor = db.execute('SELECT * FROM roles WHERE id = ?', (role_id,))
    role = cursor.fetchone()
    if not role:
        db.close()
        return jsonify({'error': 'Role not found'}), 404
    
    role_dict = dict(role)
    required_skills = json.loads(role_dict['required_skills'])
    
    # Identify gaps
    gaps = []
    for skill, required_level in required_skills.items():
        user_level = skill_vector.get(skill, 0)
        if user_level < required_level:
            gaps.append({
                'skill': skill,
                'current': user_level,
                'required': required_level,
                'gap': required_level - user_level
            })
    
    # Sort gaps by priority (largest gaps first)
    gaps.sort(key=lambda x: x['gap'], reverse=True)
    
    # Get resources for skills
    def get_resources(skill):
        cursor = db.execute('SELECT * FROM resources WHERE skill = ? LIMIT 3', (skill,))
        return [dict(row) for row in cursor.fetchall()]
    
    # Generate roadmap steps (3-5 steps)
    num_steps = min(5, max(3, len(gaps)))
    roadmap_steps = []
    
    for i in range(num_steps):
        if i >= len(gaps):
            break
        gap = gaps[i]
        resources = get_resources(gap['skill'])
        roadmap_steps.append({
            'step_number': i + 1,
            'title': f'Improve {gap["skill"]}',
            'description': f'Build your {gap["skill"]} skills from {gap["current"]:.1f} to {gap["required"]}',
            'skill': gap['skill'],
            'resources': [
                {
                    'title': r['title'],
                    'url': r['url'],
                    'type': r['type'],
                    'level': r['level']
                }
                for r in resources
            ]
        })
    
    # Save roadmap
    cursor = db.execute('''
        INSERT INTO roadmaps (session_id, role_id)
        VALUES (?, ?)
    ''', (session_id, role_id))
    roadmap_id = cursor.lastrowid
    
    # Save roadmap items
    for step in roadmap_steps:
        db.execute('''
            INSERT INTO roadmap_items (roadmap_id, step_number, title, description, skill, resources)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            roadmap_id,
            step['step_number'],
            step['title'],
            step['description'],
            step['skill'],
            json.dumps(step['resources'])
        ))
    
    db.commit()
    db.close()
    
    return jsonify({
        'roadmap_id': roadmap_id,
        'role': {
            'id': role_dict['id'],
            'name': role_dict['name'],
            'description': role_dict['description']
        },
        'steps': roadmap_steps
    })


@app.route('/api/sessions/<session_id>/roadmap', methods=['GET'])
def get_roadmap(session_id):
    """Get roadmap"""
    db = get_db()
    
    cursor = db.execute('''
        SELECT r.*, ro.name as role_name, ro.description as role_description
        FROM roadmaps r
        JOIN roles ro ON r.role_id = ro.id
        WHERE r.session_id = ?
        ORDER BY r.created_at DESC
        LIMIT 1
    ''', (session_id,))
    roadmap = cursor.fetchone()
    
    if not roadmap:
        db.close()
        return jsonify({'error': 'Roadmap not found'}), 404
    
    roadmap_dict = dict(roadmap)
    
    cursor = db.execute('''
        SELECT * FROM roadmap_items
        WHERE roadmap_id = ?
        ORDER BY step_number
    ''', (roadmap_dict['id'],))
    items = [dict(row) for row in cursor.fetchall()]
    
    items_with_resources = []
    for item in items:
        item_dict = dict(item)
        item_dict['resources'] = json.loads(item_dict['resources'] or '[]')
        items_with_resources.append(item_dict)
    
    # Calculate progress
    total_items = len(items)
    completed_items = sum(1 for item in items if item['status'] == 'completed')
    progress = round((completed_items / total_items * 100)) if total_items > 0 else 0
    
    roadmap_dict['items'] = items_with_resources
    roadmap_dict['progress'] = progress
    db.close()
    
    return jsonify(roadmap_dict)


@app.route('/api/roadmap-items/<int:item_id>', methods=['PATCH'])
def update_roadmap_item(item_id):
    """Update roadmap item status"""
    data = request.json
    status = data.get('status')
    
    db = get_db()
    
    if status == 'completed':
        db.execute('''
            UPDATE roadmap_items
            SET status = ?, completed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (status, item_id))
    else:
        db.execute('''
            UPDATE roadmap_items
            SET status = ?, completed_at = NULL
            WHERE id = ?
        ''', (status, item_id))
    
    db.commit()
    db.close()
    return jsonify({'success': True})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=True)
