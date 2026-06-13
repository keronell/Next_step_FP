from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import os
import json
import uuid
import csv
import random
import numpy as np
from pathlib import Path
from collections import defaultdict
from db import get_db

load_dotenv()

app = Flask(__name__)
CORS(app)

PORT = int(os.getenv('PORT', 3001))


@app.route('/', methods=['GET'])
def index():
    """Root endpoint - API information"""
    return jsonify({
        'message': 'NextStep Career Matcher API',
        'status': 'running',
        'version': '1.0.0',
        'endpoints': {
            'sessions': '/api/sessions',
            'questions': '/api/questions',
            'answers': '/api/sessions/<session_id>/answers',
            'compute': '/api/sessions/<session_id>/compute',
            'roadmap': '/api/sessions/<session_id>/roadmap',
            'roadmap_items': '/api/roadmap-items/<item_id>',
            'adaptive_start': '/api/adaptive/start',
            'adaptive_answer': '/api/adaptive/<session_id>/answer'
        }
    })


def compute_skill_vector(answers, db):
    """Compute skill vector from answers"""
    skill_vector = {}
    
    if not answers:
        print("Warning: No answers provided to compute_skill_vector")
        return {}
    
    for answer in answers:
        question_id = answer.get('question_id')
        if not question_id:
            continue
            
        cursor = db.execute(
            'SELECT skill_mappings, answer_type FROM questions WHERE id = ?',
            (question_id,)
        )
        question = cursor.fetchone()
        
        if not question:
            print(f"Warning: Question {question_id} not found in database")
            continue
        
        try:
            skill_mappings = json.loads(question['skill_mappings'])
        except:
            print(f"Warning: Could not parse skill_mappings for question {question_id}")
            skill_mappings = {}
        
        if not skill_mappings:
            # Skip questions without skill mappings
            continue
        
        # For Likert5: map 1-5 to 0-4 scale
        normalized_value = 0
        answer_type = question['answer_type']
        answer_value = answer.get('answer_value', '')
        
        if answer_type == 'Likert5':
            try:
                answer_value = float(answer_value) if answer_value else 0
                normalized_value = (answer_value - 1) / 4  # Maps 1->0, 5->1
            except (ValueError, TypeError):
                normalized_value = 0
        elif answer_type == 'SingleChoice':
            # For single choice, if answered, give partial credit
            normalized_value = 0.5 if answer_value and answer_value != 'Not sure' else 0
        elif answer_type == 'MultiChoice':
            # For multi choice, count selections (comma-separated)
            selections = [v for v in answer_value.split(',') if v and v != 'Not sure'] if answer_value else []
            normalized_value = min(len(selections) * 0.3, 1)  # Up to 1.0 for multiple selections
        elif answer_type == 'Numeric':
            # Normalize numeric (e.g., hours per week: 0-40 -> 0-1)
            try:
                answer_value = float(answer_value) if answer_value else 0
                normalized_value = min(answer_value / 40, 1)
            except (ValueError, TypeError):
                normalized_value = 0
        
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
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        role_id = data.get('role_id')
        if not role_id:
            return jsonify({'error': 'role_id is required'}), 400
        
        db = get_db()
        
        # Get user skill vector (same as standard quiz)
        cursor = db.execute('SELECT skill_vector, completed_at FROM sessions WHERE id = ?', (session_id,))
        session = cursor.fetchone()
        
        if not session:
            db.close()
            return jsonify({'error': 'Session not found'}), 404
        
        # Get skill vector - same handling as standard quiz
        skill_vector = {}
        if session['skill_vector']:
            try:
                skill_vector = json.loads(session['skill_vector'])
            except Exception as e:
                print(f"Error parsing skill_vector: {e}")
                skill_vector = {}
        
        print(f"Roadmap generation - session_id: {session_id}, skill_vector: {skill_vector}")
        
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
            # If skill_vector is empty (adaptive quiz without skill_mappings), assume user has 0 in all skills
            if user_level < required_level:
                gaps.append({
                    'skill': skill,
                    'current': user_level,
                    'required': required_level,
                    'gap': required_level - user_level
                })
        
        # If no gaps found (user meets all requirements), show top skills as areas to maintain/improve
        if not gaps and required_skills:
            # Show top 3-5 required skills as learning areas
            sorted_skills = sorted(required_skills.items(), key=lambda x: x[1], reverse=True)
            for skill, required_level in sorted_skills[:5]:
                gaps.append({
                    'skill': skill,
                    'current': required_level,
                    'required': required_level,
                    'gap': 0
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
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"\n{'='*60}")
        print(f"ERROR in generate_roadmap: {str(e)}")
        print(f"{'='*60}")
        print(error_trace)
        print(f"{'='*60}\n")
        if 'db' in locals():
            try:
                db.close()
            except:
                pass
        return jsonify({
            'error': f'Server error: {str(e)}',
            'details': error_trace.split('\n')[-2] if error_trace else None
        }), 500


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


# ============================================================================
# Adaptive Quiz Functions
# ============================================================================

def load_expert_answers():
    """Load expert answers database"""
    data_dir = Path(__file__).parent / 'data'
    
    by_question_file = data_dir / 'expert_answers_by_question.json'
    by_job_file = data_dir / 'expert_answers_by_job.json'
    
    if not by_question_file.exists() or not by_job_file.exists():
        return None, None
    
    with open(by_question_file, 'r') as f:
        by_question = json.load(f)
    
    with open(by_job_file, 'r') as f:
        by_job = json.load(f)
    
    return by_question, by_job


def load_adaptive_config():
    """Load adaptive quiz configuration"""
    config_file = Path(__file__).parent / 'config' / 'adaptive_quiz_config.json'
    if config_file.exists():
        with open(config_file, 'r') as f:
            return json.load(f)
    # Default config
    return {
        "warmup_questions": 3,
        "max_questions": 20,
        "min_questions": 10,
        "target_jobs_remaining": 5,
        "elimination_threshold": 0.3,
        "early_stop_threshold": 7
    }


def generate_skill_mappings_simple(question_text: str) -> dict:
    """Generate skill mappings based on question content (simplified version)"""
    mappings = {}
    question_lower = question_text.lower()
    
    # Map questions to skills based on keywords
    if any(word in question_lower for word in ['ui', 'interface', 'visual', 'design', 'layout']):
        mappings['UI/UX Design'] = 0.8
        mappings['Frontend Development'] = 0.5
    
    if any(word in question_lower for word in ['workflow', 'automate', 'prototype', 'optimize', 'performance']):
        mappings['Problem Solving'] = 0.7
        mappings['Backend Development'] = 0.4
    
    if any(word in question_lower for word in ['product', 'feature', 'priorit']):
        mappings['Product Management'] = 0.6
        mappings['Problem Solving'] = 0.4
    
    if any(word in question_lower for word in ['write', 'story', 'blog', 'explain', 'document']):
        mappings['Technical Writing'] = 0.8
        mappings['Communication'] = 0.5
    
    if any(word in question_lower for word in ['brainstorm', 'solution', 'problem', 'reasoning', 'analyze']):
        mappings['Problem Solving'] = 0.7
        mappings['Critical Thinking'] = 0.5
    
    if any(word in question_lower for word in ['data', 'outlier', 'statistic', 'analyze']):
        mappings['Data Analysis'] = 0.8
        mappings['Problem Solving'] = 0.5
    
    if any(word in question_lower for word in ['team', 'collaborate', 'discuss', 'group']):
        mappings['Communication'] = 0.7
        mappings['Teamwork'] = 0.5
    
    # Default mappings if none found
    if not mappings:
        mappings['Problem Solving'] = 0.5
        mappings['Communication'] = 0.3
    
    return mappings


def ensure_question_in_db(db, question_id: int, question_bank_path: Path = None):
    """Ensure a question exists in the database, loading from CSV if needed"""
    # Check if question exists
    cursor = db.execute('SELECT id FROM questions WHERE id = ?', (question_id,))
    if cursor.fetchone():
        return True  # Question already exists
    
    # Question doesn't exist, load from question bank
    if question_bank_path is None:
        question_bank_path = Path(__file__).parent.parent / 'data' / 'data' / 'question_bank.csv'
    
    if not question_bank_path.exists():
        return False
    
    try:
        with open(question_bank_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for q in reader:
                if str(q.get('id')) == str(question_id):
                    # Found the question, generate skill mappings
                    question_text = q.get('question', '')
                    skill_mappings = generate_skill_mappings_simple(question_text)
                    
                    # Insert it with generated skill mappings
                    db.execute('''
                        INSERT OR IGNORE INTO questions 
                        (id, question, category, subcategory, answer_type, options, skill_mappings)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        int(q['id']),
                        question_text,
                        q.get('category', 'General'),
                        q.get('subcategory', 'General'),
                        q.get('answer_type', 'Likert5'),
                        q.get('options', ''),
                        json.dumps(skill_mappings)  # Generate skill mappings
                    ))
                    db.commit()
                    return True
    except Exception as e:
        print(f"Error loading question {question_id} from CSV: {e}")
        return False
    
    return False


def normalize_answer(answer_value: str, answer_type: str) -> float:
    """Normalize answer to 0-1 scale for comparison"""
    if not answer_value:
        return 0
    
    try:
        if answer_type == 'Likert5':
            return (float(answer_value) - 1) / 4  # 1->0, 5->1
        elif answer_type == 'SingleChoice':
            return 0.5 if answer_value and answer_value != 'Not sure' else 0
        elif answer_type == 'MultiChoice':
            selections = [v for v in answer_value.split(',') if v] if answer_value else []
            return min(len(selections) * 0.3, 1)
        elif answer_type == 'Numeric':
            return min(float(answer_value) / 40, 1) if answer_value else 0
    except (ValueError, TypeError):
        return 0
    return 0


def calculate_similarity(user_answer: str, expert_answer: str, answer_type: str) -> float:
    """Calculate similarity between user and expert answer (0-1)"""
    user_norm = normalize_answer(user_answer, answer_type)
    expert_norm = normalize_answer(expert_answer, answer_type)
    
    # Use 1 - absolute difference as similarity
    similarity = 1 - abs(user_norm - expert_norm)
    return max(0, similarity)


def compute_job_scores(user_answers: list, remaining_jobs: list, 
                      expert_by_question: dict) -> dict:
    """Compute similarity scores for each remaining job"""
    job_scores = defaultdict(float)
    job_answer_counts = defaultdict(int)
    
    if not user_answers:
        print("Warning: No user answers provided to compute_job_scores")
        return {}
    
    if not remaining_jobs:
        print("Warning: No remaining jobs provided to compute_job_scores")
        return {}
    
    for answer in user_answers:
        q_id = str(answer['question_id'])
        user_answer_value = answer['answer_value']
        answer_type = answer.get('answer_type', 'Likert5')
        
        # Get expert answers for this question
        expert_answers = expert_by_question.get(q_id, {})
        
        if not expert_answers:
            # Debug: question not found in expert answers
            continue
        
        for job_id in remaining_jobs:
            if job_id in expert_answers:
                expert_answer = expert_answers[job_id]
                similarity = calculate_similarity(user_answer_value, expert_answer, answer_type)
                job_scores[job_id] += similarity
                job_answer_counts[job_id] += 1
    
    # Average scores
    for job_id in job_scores:
        if job_answer_counts[job_id] > 0:
            job_scores[job_id] /= job_answer_counts[job_id]
    
    # Debug output
    if not job_scores:
        print(f"Warning: compute_job_scores returned empty scores")
        print(f"  User answers: {len(user_answers)}")
        print(f"  Remaining jobs: {remaining_jobs}")
        print(f"  Sample question IDs: {[str(a['question_id']) for a in user_answers[:3]]}")
        print(f"  Expert answers keys: {list(expert_by_question.keys())[:5]}")
    
    return dict(job_scores)


def eliminate_jobs(job_scores: dict, threshold: float = 0.3) -> list:
    """Eliminate jobs with scores below threshold"""
    return [job_id for job_id, score in job_scores.items() if score >= threshold]


def select_next_question(remaining_jobs: list, answered_questions: list,
                        expert_by_question: dict) -> dict:
    """Select next question that best differentiates remaining jobs"""
    question_bank = Path(__file__).parent.parent / 'data' / 'data' / 'question_bank.csv'
    
    if not question_bank.exists():
        return None
    
    # Load all questions
    with open(question_bank, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        all_questions = list(reader)
    
    # Get answered question IDs
    answered_q_ids = {str(a['question_id']) for a in answered_questions}
    
    # Find unasked questions
    unasked_questions = [q for q in all_questions if str(q['id']) not in answered_q_ids]
    
    if not unasked_questions:
        return None
    
    # If we have few jobs left, pick question with highest variance in expert answers
    best_question = None
    best_variance = 0
    
    for question in unasked_questions:
        q_id = str(question['id'])
        expert_answers = expert_by_question.get(q_id, {})
        
        # Get answers for remaining jobs
        answers = [expert_answers.get(job_id) for job_id in remaining_jobs 
                  if job_id in expert_answers]
        
        if len(answers) < 2:
            continue
        
        # Calculate variance (higher = more differentiation)
        try:
            numeric_answers = [float(a) for a in answers if a]
            if numeric_answers:
                variance = np.var(numeric_answers)
                if variance > best_variance:
                    best_variance = variance
                    best_question = question
        except (ValueError, TypeError):
            continue
    
    # Fallback to random if no good question found
    if not best_question:
        best_question = random.choice(unasked_questions)
    
    return {
        'id': best_question['id'],
        'question': best_question['question'],
        'answer_type': best_question['answer_type'],
        'options': best_question.get('options', '')
    }


@app.route('/api/adaptive/start', methods=['POST'])
def start_adaptive_quiz():
    """Start adaptive quiz session"""
    db = get_db()
    
    # Get top 10 jobs
    top_jobs_file = Path(__file__).parent / 'data' / 'top_10_jobs.json'
    if not top_jobs_file.exists():
        db.close()
        return jsonify({'error': 'Top 10 jobs not found. Run select_top_jobs.py first.'}), 404
    
    with open(top_jobs_file, 'r') as f:
        top_jobs = json.load(f)
    
    # Create session
    session_id = str(uuid.uuid4())
    db.execute('''
        INSERT INTO sessions (id, created_at, adaptive_mode, remaining_jobs)
        VALUES (?, CURRENT_TIMESTAMP, 1, ?)
    ''', (session_id, json.dumps([job['id'] for job in top_jobs])))
    db.commit()
    
    # Select first question
    question_bank = Path(__file__).parent.parent / 'data' / 'data' / 'question_bank.csv'
    if not question_bank.exists():
        db.close()
        return jsonify({'error': 'Question bank not found'}), 404
    
    with open(question_bank, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        questions = list(reader)
        if not questions:
            db.close()
            return jsonify({'error': 'No questions found'}), 404
        first_question = questions[0]  # Start with first question
    
    db.close()
    
    return jsonify({
        'session_id': session_id,
        'remaining_jobs': len(top_jobs),
        'question': {
            'id': first_question['id'],
            'question': first_question['question'],
            'answer_type': first_question['answer_type'],
            'options': first_question.get('options', '')
        }
    })


@app.route('/api/adaptive/<session_id>/answer', methods=['POST'])
def submit_adaptive_answer(session_id):
    """Submit answer and get next question or results"""
    try:
        db = get_db()
        data = request.json
        
        if not data:
            db.close()
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate required fields
        if 'question_id' not in data:
            db.close()
            return jsonify({'error': 'question_id is required'}), 400
        if 'answer_value' not in data:
            db.close()
            return jsonify({'error': 'answer_value is required'}), 400
        
        # Get session
        cursor = db.execute('SELECT remaining_jobs FROM sessions WHERE id = ?', (session_id,))
        session = cursor.fetchone()
        if not session:
            db.close()
            return jsonify({'error': 'Session not found'}), 404
        
        remaining_jobs = json.loads(session['remaining_jobs'] or '[]')
        
        # Save answer - ensure question_id is converted to int for database (schema expects INTEGER)
        answer_type = data.get('answer_type', 'Likert5')
        try:
            question_id = int(data['question_id'])  # Convert to int for database
        except (ValueError, TypeError):
            db.close()
            return jsonify({'error': f'Invalid question_id: {data.get("question_id")}'}), 400
        
        answer_value = str(data['answer_value'])  # Ensure it's a string
        
        # Ensure question exists in database (for foreign key constraint)
        question_bank_path = Path(__file__).parent.parent / 'data' / 'data' / 'question_bank.csv'
        if not ensure_question_in_db(db, question_id, question_bank_path):
            db.close()
            return jsonify({'error': f'Question {question_id} not found in question bank'}), 404
        
        try:
            db.execute('''
                INSERT INTO answers (session_id, question_id, answer_value, answer_type)
                VALUES (?, ?, ?, ?)
            ''', (session_id, question_id, answer_value, answer_type))
            db.commit()
        except Exception as e:
            db.rollback()
            db.close()
            return jsonify({'error': f'Failed to save answer: {str(e)}'}), 500
    
        # Get all user answers - convert question_id to string for consistency
        cursor = db.execute('''
            SELECT question_id, answer_value, answer_type
            FROM answers WHERE session_id = ?
        ''', (session_id,))
        user_answers = []
        for row in cursor.fetchall():
            answer_dict = dict(row)
            answer_dict['question_id'] = str(answer_dict['question_id'])  # Ensure string
            user_answers.append(answer_dict)
        
        # Load config
        config = load_adaptive_config()
        warmup_questions = config.get('warmup_questions', 3)
        questions_answered = len(user_answers)
        
        # Load expert answers
        try:
            expert_by_question, expert_by_job = load_expert_answers()
            if not expert_by_question:
                db.close()
                return jsonify({'error': 'Expert answers not found. Run create_expert_database.py first.'}), 500
        except Exception as e:
            db.close()
            import traceback
            print(f"Error loading expert answers: {str(e)}")
            print(traceback.format_exc())
            return jsonify({'error': f'Failed to load expert answers: {str(e)}'}), 500
    
        # Only start eliminating after warmup period
        if questions_answered >= warmup_questions:
            try:
                # Compute job scores
                job_scores = compute_job_scores(user_answers, remaining_jobs, expert_by_question)
                
                # Eliminate low-scoring jobs
                threshold = config.get('elimination_threshold', 0.3)
                new_remaining = eliminate_jobs(job_scores, threshold)
                
                # Update remaining jobs
                remaining_jobs = new_remaining
                db.execute('UPDATE sessions SET remaining_jobs = ? WHERE id = ?',
                           (json.dumps(remaining_jobs), session_id))
                db.commit()
            except Exception as e:
                import traceback
                print(f"Error computing job scores: {str(e)}")
                print(traceback.format_exc())
                # Fallback: don't eliminate, just continue
                job_scores = {}
                for job_id in remaining_jobs:
                    job_scores[job_id] = 0.5
        else:
            # Still in warmup - don't eliminate, just collect answers
            job_scores = {}
            for job_id in remaining_jobs:
                job_scores[job_id] = 0.5  # Neutral score during warmup
        
        # Check if we should stop
        max_questions = config.get('max_questions', 20)
        min_questions = config.get('min_questions', 10)
        target_jobs = config.get('target_jobs_remaining', 5)
        early_stop_threshold = config.get('early_stop_threshold', 7)
        
        should_stop = (
            len(remaining_jobs) <= target_jobs or  # Target jobs reached
            questions_answered >= max_questions or  # Max questions reached
            (len(remaining_jobs) <= early_stop_threshold and questions_answered >= min_questions)  # Early stop
        )
        
        if should_stop:
            # Compute final scores if not already computed
            if questions_answered < warmup_questions or not job_scores:
                job_scores = compute_job_scores(user_answers, remaining_jobs, expert_by_question)
            
            # If no scores computed, compute for all remaining jobs
            if not job_scores and remaining_jobs:
                print("Recomputing job scores as they were empty")
                job_scores = compute_job_scores(user_answers, remaining_jobs, expert_by_question)
            
            # Debug: print scores
            print(f"Final job_scores: {job_scores}")
            print(f"Remaining jobs: {remaining_jobs}")
            
            # Get top 5 jobs - if we have scores, use them; otherwise use all remaining jobs
            if job_scores:
                sorted_jobs = sorted(job_scores.items(), key=lambda x: x[1], reverse=True)
                print(f"Sorted jobs: {sorted_jobs[:5]}")
                top_5_job_ids = [job_id for job_id, _ in sorted_jobs[:5]]
            else:
                # Fallback: use all remaining jobs
                print("Warning: No job scores, using all remaining jobs")
                top_5_job_ids = remaining_jobs[:5]
            
            # Get full job details
            top_jobs_file = Path(__file__).parent / 'data' / 'top_10_jobs.json'
            if not top_jobs_file.exists():
                db.close()
                return jsonify({'error': 'Top 10 jobs file not found'}), 500
            
            with open(top_jobs_file, 'r') as f:
                all_jobs = json.load(f)
            
            top_5_jobs = [job for job in all_jobs if job['id'] in top_5_job_ids]
            
            # Sort by score if we have scores
            if job_scores:
                top_5_jobs = sorted(top_5_jobs, 
                                  key=lambda j: job_scores.get(j['id'], 0), 
                                  reverse=True)
            
            # Add scores to jobs - ensure we have valid scores
            for job in top_5_jobs:
                score = job_scores.get(job['id'], 0) if job_scores else 0.5  # Default to 50% if no scores
                match_score = round(score * 100, 1)
                job['match_score'] = match_score
                # Also set score field for compatibility
                job['score'] = match_score
                print(f"Job {job['id']} ({job['name']}): score={score}, match_score={match_score}")
                # Remove reasons field if it exists (adaptive quiz doesn't use skill-based reasons)
                if 'reasons' in job:
                    del job['reasons']
            
            # Compute and store skill vector for roadmap generation (same as standard quiz)
            # Get all answers for skill vector computation - use same format as standard quiz
            cursor = db.execute('''
                SELECT a.question_id, a.answer_value
                FROM answers a
                WHERE a.session_id = ?
            ''', (session_id,))
            all_answers = [dict(row) for row in cursor.fetchall()]
            
            print(f"Computing skill vector from {len(all_answers)} answers")
            
            # Compute skill vector from answers (same function as standard quiz)
            try:
                skill_vector = compute_skill_vector(all_answers, db)
                print(f"Computed skill vector: {skill_vector}")
            except Exception as e:
                import traceback
                print(f"Error computing skill vector: {e}")
                print(traceback.format_exc())
                skill_vector = {}  # Fallback to empty vector
            
            # Store skill vector and mark session complete (same as standard quiz)
            db.execute('''
                UPDATE sessions 
                SET completed_at = CURRENT_TIMESTAMP, skill_vector = ?
                WHERE id = ?
            ''', (json.dumps(skill_vector), session_id))
            db.commit()
            db.close()
            
            return jsonify({
                'completed': True,
                'top_5_jobs': top_5_jobs,
                'questions_answered': questions_answered
            })
        else:
            # Select next question
            try:
                next_question = select_next_question(remaining_jobs, user_answers, expert_by_question)
            except Exception as e:
                import traceback
                print(f"Error selecting next question: {str(e)}")
                print(traceback.format_exc())
                db.close()
                return jsonify({'error': f'Failed to select next question: {str(e)}'}), 500
            
            if not next_question:
                db.close()
                return jsonify({'error': 'No more questions available'}), 400
            
            db.close()
            
            return jsonify({
                'completed': False,
                'remaining_jobs': len(remaining_jobs),
                'questions_answered': questions_answered,
                'warmup_active': questions_answered < warmup_questions,
                'question': next_question
            })
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        error_msg = str(e)
        print(f"\n{'='*60}")
        print(f"ERROR in submit_adaptive_answer: {error_msg}")
        print(f"{'='*60}")
        print(error_trace)
        print(f"{'='*60}\n")
        if 'db' in locals():
            try:
                db.close()
            except:
                pass
        return jsonify({
            'error': f'Server error: {error_msg}',
            'details': error_trace.split('\n')[-2] if error_trace else None
        }), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=True)
