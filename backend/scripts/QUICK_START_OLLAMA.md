# Quick Start with Ollama

Based on your logs, Ollama is running! Here's how to use it:

## Your Setup
- ✅ Ollama 0.15.0 is running
- ✅ Server on 127.0.0.1:11434
- ✅ Apple M2 Pro with 11.8 GiB GPU (Metal support)
- ✅ Low VRAM mode active (normal for M2 Pro)

## Step 1: Install a Model

Open a **new terminal** (keep Ollama running) and install a model:

```bash
# Recommended for M2 Pro (good balance of speed/quality):
ollama pull llama3.2

# OR for better quality (slower):
ollama pull llama3.1:8b

# OR alternative:
ollama pull mistral
```

**Note:** Models are ~2-5GB, so download may take a few minutes.

## Step 2: Verify Model is Installed

```bash
ollama list
```

You should see your model listed.

## Step 3: Test the Connection

```bash
cd backend/scripts
python3 test_ollama.py
```

This will verify Ollama is working correctly.

## Step 4: Generate Expert Answers

```bash
cd backend/scripts

# Set provider to Ollama
export AI_PROVIDER=ollama
export OLLAMA_MODEL=llama3.2  # or your chosen model

# Make sure you've run Step 1 first (select_top_jobs.py)
python3 generate_expert_answers_free.py
```

## Troubleshooting

### "Cannot connect to Ollama server"
- Make sure `ollama serve` is still running in another terminal
- Wait a few seconds after starting Ollama for it to fully initialize
- Check: `curl http://127.0.0.1:11434/api/tags`

### "Model not found"
- Install the model: `ollama pull llama3.2`
- List installed models: `ollama list`

### Slow Performance
- This is normal for local models
- For ~16,000 questions, expect several hours
- You can run it overnight
- Consider using Groq (cloud, faster) if speed is critical

### Out of Memory
- Use smaller model: `llama3.2` instead of `llama3.1:8b`
- Close other applications
- Your M2 Pro should handle `llama3.2` fine

## Performance Expectations

With Ollama on M2 Pro:
- **Speed**: ~2-5 seconds per answer
- **Total time**: ~9-22 hours for 16,000 questions
- **Cost**: $0 (completely free!)

**Tip:** Run overnight or use a smaller test set first:
- Test with 10 questions: Modify script to use `questions[:10]`
- Then run full dataset when confident

## Alternative: Use Groq (Faster, Still Free)

If you want faster results:

```bash
# Get free API key from https://console.groq.com/
export GROQ_API_KEY="your-key-here"
export AI_PROVIDER=groq

python3 generate_expert_answers_free.py
```

Groq is much faster (~0.5s per answer) but requires internet and API key.

## Next Steps

Once expert answers are generated:
1. Run `create_expert_database.py` to create lookup files
2. Start the backend server
3. Test the adaptive quiz!
