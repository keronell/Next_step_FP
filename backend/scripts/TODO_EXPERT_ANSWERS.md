# TODO: Expert Answers Generation Improvements

## Current Issues Identified

### Critical Issues
- [ ] **88.4% of Likert5 answers are "4"** - Model defaults to middle value, reducing differentiation
- [ ] **1,195 malformed JSON responses** - Responses starting with "{" indicate parsing failures
- [ ] **Low answer diversity** - Only 11.6% of answers use values other than "4"
- [ ] **Poor job differentiation** - Similar answer patterns across all jobs

### Answer Distribution (Current)
- Answer "4": 12,882 occurrences (88.4%)
- Answer "3": 153 occurrences (1.1%)
- Answer "5": 280 occurrences (2.0%)
- Answer "1": 53 occurrences (0.4%)
- Answer "2": 4 occurrences (0.03%)
- Malformed: 1,195 occurrences (8.2%)

---

## Prompt Engineering Improvements

### 1. Enhance System Prompt
- [ ] Add explicit instruction to use full range (1-5) based on job perspective
- [ ] Include examples showing different answer values for different job roles
- [ ] Emphasize that "4" should only be used when truly appropriate
- [ ] Add instruction: "Use the full scale: 1=Strongly Disagree, 2=Disagree, 3=Neutral, 4=Agree, 5=Strongly Agree"

**Suggested System Prompt:**
```
You are an expert {job['name']}. Answer authentically from your professional perspective.
Use the full 1-5 scale based on how strongly this applies to your role:
- 1: Strongly Disagree (rarely/never relevant)
- 2: Disagree (not typically relevant)
- 3: Neutral (sometimes relevant)
- 4: Agree (often relevant)
- 5: Strongly Agree (very relevant/essential)
```

### 2. Improve User Prompt
- [ ] Add context about why the answer matters for this specific job
- [ ] Include examples of when to use different values
- [ ] Add instruction to think about job-specific scenarios before answering
- [ ] Request justification reasoning (even if not returned, helps model think)

**Suggested User Prompt Enhancement:**
```
Expert Context: {job['description']}
Key Skills: {skills}

Question: {q['question']}
Type: {q['answer_type']}
Options: {q.get('options', 'N/A')}

Think about: How relevant is this question to a {job['name']}?
- If this is core to your role, use 4-5
- If this is peripheral, use 1-2
- If this is sometimes relevant, use 3

Provide ONLY the numeric value (1-5 for Likert5):
```

### 3. Add Few-Shot Examples
- [ ] Include 2-3 examples showing different jobs giving different answers to the same question
- [ ] Show examples where Frontend Developer gives 5, Backend Developer gives 2
- [ ] Demonstrate proper JSON format in examples

---

## Technical Improvements

### 4. Increase Temperature
- [ ] Change temperature from 0.1 to 0.7-0.9 for more diverse responses
- [ ] Test different temperature values (0.5, 0.7, 0.9) to find optimal balance
- [ ] Consider using temperature=0.3 for structured output, but add randomness in post-processing

**Current:** `options={'temperature': 0.1, 'stop': ["\n"]}`
**Suggested:** `options={'temperature': 0.7, 'stop': ["\n"]}`

### 5. Improve JSON Parsing
- [ ] Better handling of malformed responses (1,195 cases)
- [ ] Add validation to detect and retry on malformed JSON
- [ ] Implement fallback parsing for edge cases
- [ ] Log malformed responses for analysis

**Current Issue:** Responses starting with "{" suggest incomplete JSON
**Fix:** Add retry logic with clearer JSON schema instructions

### 6. Add Answer Validation
- [ ] Validate that Likert5 answers are in range 1-5
- [ ] Reject and retry if answer is out of range
- [ ] Add statistics tracking for answer distribution per job
- [ ] Alert if a job's answers are too uniform

### 7. Implement Answer Diversity Checks
- [ ] Add post-processing to detect if answers are too uniform
- [ ] Flag jobs with >80% same answer value
- [ ] Implement re-generation for questions with poor diversity
- [ ] Add diversity metrics to checkpoint file

---

## Quality Assurance

### 8. Add Sampling Strategy
- [ ] Implement stratified sampling to ensure answer diversity
- [ ] Force at least 20% of answers to be 1-2, 20% to be 5
- [ ] Use weighted random selection if model is too uniform
- [ ] Add manual review step for edge cases

### 9. Job-Specific Answer Patterns
- [ ] Analyze which questions should have different answers per job
- [ ] Create expected answer patterns (e.g., Frontend should give 5 to UI questions)
- [ ] Validate that jobs differ on key differentiating questions
- [ ] Add unit tests for expected job-specific answer patterns

### 10. Post-Processing Improvements
- [ ] Add answer normalization for edge cases
- [ ] Implement answer smoothing to reduce extreme uniformity
- [ ] Add validation that answers make sense for job type
- [ ] Create answer quality score

---

## Model Configuration

### 11. Try Different Models
- [ ] Test with different Ollama models (llama3.1, mistral, qwen variants)
- [ ] Compare answer diversity across models
- [ ] Document which model gives best results
- [ ] Consider using larger models for better reasoning

### 12. Adjust Model Parameters
- [ ] Experiment with `top_p` parameter (nucleus sampling)
- [ ] Try `top_k` parameter for more controlled diversity
- [ ] Test `repeat_penalty` to avoid repetitive answers
- [ ] Fine-tune parameters per question type

**Suggested Options:**
```python
options={
    'temperature': 0.7,
    'top_p': 0.9,
    'top_k': 40,
    'repeat_penalty': 1.1,
    'stop': ["\n"]
}
```

---

## Data Analysis & Monitoring

### 13. Add Answer Statistics
- [ ] Track answer distribution per job
- [ ] Generate report showing answer diversity metrics
- [ ] Create visualization of answer patterns
- [ ] Alert on low diversity (<20% non-4 answers)

### 14. Quality Metrics
- [ ] Calculate answer diversity score (entropy)
- [ ] Measure job differentiation (how different are job answers)
- [ ] Track malformed response rate
- [ ] Monitor answer distribution over time

### 15. Validation Script
- [ ] Create script to analyze expert_answers.json
- [ ] Check for answer diversity per job
- [ ] Validate that jobs have different answer patterns
- [ ] Generate quality report

---

## Implementation Priority

### High Priority (Fix Now)
1. ✅ Increase temperature to 0.7-0.9
2. ✅ Improve system prompt with full scale explanation
3. ✅ Fix JSON parsing for malformed responses
4. ✅ Add answer validation (1-5 range check)

### Medium Priority (Next Sprint)
5. Add few-shot examples in prompt
6. Implement answer diversity checks
7. Add retry logic for malformed responses
8. Create validation script

### Low Priority (Future)
9. Try different models
10. Implement stratified sampling
11. Add post-processing smoothing
12. Create quality metrics dashboard

---

## Testing Plan

### 16. Test Improvements
- [ ] Run small batch (100 questions) with new prompt
- [ ] Compare answer distribution before/after
- [ ] Verify answer diversity improved
- [ ] Check that jobs still have distinct patterns

### 17. Validation Tests
- [ ] Test that Frontend gives high scores to UI questions
- [ ] Test that Backend gives high scores to API/DB questions
- [ ] Verify that different jobs have different answer patterns
- [ ] Check that answer distribution is more balanced

### 18. Regression Tests
- [ ] Ensure existing adaptive quiz still works
- [ ] Verify job scores are still computed correctly
- [ ] Test that answer format is still compatible
- [ ] Check that no breaking changes introduced

---

## Documentation

### 19. Update Documentation
- [ ] Document new prompt structure
- [ ] Explain answer diversity requirements
- [ ] Add troubleshooting guide for common issues
- [ ] Create guide for interpreting answer quality metrics

### 20. Add Comments
- [ ] Add inline comments explaining prompt choices
- [ ] Document why temperature was set to specific value
- [ ] Explain answer validation logic
- [ ] Comment on diversity checks

---

## Notes

### Current Prompt Analysis
The current prompt says "Answer authentically and ONLY with the final value" but doesn't:
- Explain the scale meaning
- Encourage use of full range
- Provide examples
- Give context about when to use different values

### Expected Improvements
After implementing these changes, we should see:
- Answer "4" usage drop from 88.4% to <50%
- More balanced distribution across 1-5
- Better job differentiation
- Fewer malformed responses

### Success Criteria
- [ ] Answer "4" usage < 50%
- [ ] Each value (1-5) has at least 10% representation
- [ ] Jobs show distinct answer patterns
- [ ] Malformed response rate < 1%

---

## Quick Fixes (Can Implement Immediately)

1. **Change temperature:**
   ```python
   options={'temperature': 0.7, 'stop': ["\n"]}
   ```

2. **Update system prompt:**
   ```python
   system_prompt = f"""You are an expert {job['name']}. 
   Use the full 1-5 scale: 1=Strongly Disagree, 2=Disagree, 3=Neutral, 4=Agree, 5=Strongly Agree.
   Answer based on how relevant this is to your role."""
   ```

3. **Add answer validation:**
   ```python
   if q['answer_type'] == 'Likert5':
       answer_value = int(data.answer) if data.answer.isdigit() else 3
       if answer_value < 1 or answer_value > 5:
           answer_value = 3  # Default to neutral if invalid
       data.answer = str(answer_value)
   ```

---

**Last Updated:** 2026-01-24
**Status:** Analysis Complete - Ready for Implementation
