# Free AI Providers Setup Guide

This guide explains how to use **FREE** AI providers to generate expert answers instead of paid OpenAI API.

## Quick Start

### Option 1: Ollama (Recommended - Completely Free, Local)

**Ollama runs models locally on your machine - no API keys, no costs, no rate limits!**

1. **Install Ollama:**
   ```bash
   # macOS
   brew install ollama
   # OR download from https://ollama.ai
   
   # Linux
   curl -fsSL https://ollama.ai/install.sh | sh
   ```

2. **Start Ollama:**
   ```bash
   ollama serve
   ```

3. **Download a model (in another terminal):**
   ```bash
   # Recommended models (pick one):
   ollama pull llama3.2        # Small, fast (2GB)
   ollama pull llama3.1:8b     # Better quality (4.7GB)
   ollama pull mistral         # Alternative (4GB)
   ```

4. **Run the script:**
   ```bash
   export AI_PROVIDER=ollama
   export OLLAMA_MODEL=llama3.2  # or your chosen model
   python3 generate_expert_answers_free.py
   ```

**Pros:**
- ✅ Completely free
- ✅ No API keys needed
- ✅ No rate limits
- ✅ Works offline
- ✅ Privacy (data stays local)

**Cons:**
- ⚠️ Requires local installation
- ⚠️ Needs ~4-8GB RAM for models
- ⚠️ Slower than cloud APIs (but still reasonable)

---

### Option 2: Groq (Free Tier - Very Fast)

**Groq offers free tier with very fast inference speeds.**

1. **Get API key:**
   - Sign up at https://console.groq.com/
   - Get free API key from dashboard

2. **Set environment variable:**
   ```bash
   export GROQ_API_KEY="your-api-key-here"
   export AI_PROVIDER=groq
   ```

3. **Run:**
   ```bash
   python3 generate_expert_answers_free.py
   ```

**Pros:**
- ✅ Free tier available
- ✅ Very fast (faster than OpenAI)
- ✅ Good quality models

**Cons:**
- ⚠️ Requires API key
- ⚠️ Rate limits on free tier

---

### Option 3: Hugging Face (Free Tier)

1. **Get API key:**
   - Sign up at https://huggingface.co/
   - Go to Settings → Access Tokens
   - Create a token

2. **Set environment variables:**
   ```bash
   export HUGGINGFACE_API_KEY="your-token-here"
   export AI_PROVIDER=huggingface
   ```

3. **Run:**
   ```bash
   python3 generate_expert_answers_free.py
   ```

**Pros:**
- ✅ Free tier available
- ✅ Many model options

**Cons:**
- ⚠️ Can be slower
- ⚠️ Rate limits on free tier

---

### Option 4: Google Gemini (Free Tier)

1. **Get API key:**
   - Go to https://makersuite.google.com/app/apikey
   - Create free API key

2. **Set environment variables:**
   ```bash
   export GEMINI_API_KEY="your-api-key-here"
   export AI_PROVIDER=gemini
   ```

3. **Run:**
   ```bash
   python3 generate_expert_answers_free.py
   ```

**Pros:**
- ✅ Free tier available
- ✅ Good quality

**Cons:**
- ⚠️ Rate limits on free tier

---

### Option 5: Together AI (Free Tier)

1. **Get API key:**
   - Sign up at https://api.together.xyz/
   - Get API key from dashboard

2. **Set environment variables:**
   ```bash
   export TOGETHER_API_KEY="your-api-key-here"
   export AI_PROVIDER=together
   ```

3. **Run:**
   ```bash
   python3 generate_expert_answers_free.py
   ```

---

## Installation

Install required dependencies:

```bash
pip install requests
```

(No OpenAI package needed for free providers!)

---

## Provider Comparison

| Provider | Cost | Speed | Quality | Setup Difficulty |
|----------|------|-------|---------|------------------|
| **Ollama** | Free | Medium | Good | Easy |
| **Groq** | Free tier | Very Fast | Good | Easy |
| **Hugging Face** | Free tier | Slow | Good | Easy |
| **Gemini** | Free tier | Fast | Excellent | Easy |
| **Together AI** | Free tier | Fast | Good | Easy |

---

## Recommended Setup

**For best experience: Use Ollama**

1. It's completely free with no limits
2. No API keys to manage
3. Works offline
4. Privacy-friendly (all processing local)

**Setup steps:**
```bash
# 1. Install Ollama
brew install ollama  # macOS
# OR download from https://ollama.ai

# 2. Start Ollama service
ollama serve

# 3. Download model (in new terminal)
ollama pull llama3.2

# 4. Run script
export AI_PROVIDER=ollama
python3 generate_expert_answers_free.py
```

---

## Troubleshooting

### Ollama: "Connection refused"
- Make sure `ollama serve` is running
- Check if Ollama is running: `curl http://localhost:11434/api/tags`

### Ollama: Model not found
- Download the model: `ollama pull llama3.2`
- List available models: `ollama list`

### API Rate Limits
- Ollama: No limits (local)
- Others: Wait or upgrade to paid tier

### Slow Performance
- Ollama: Use smaller model (llama3.2 instead of llama3.1:8b)
- Groq: Usually fastest option
- Consider running overnight for large datasets

---

## Switching Providers

Change provider by setting environment variable:

```bash
export AI_PROVIDER=ollama      # Local, free
export AI_PROVIDER=groq        # Fast, free tier
export AI_PROVIDER=gemini      # Good quality, free tier
export AI_PROVIDER=huggingface # Many models, free tier
export AI_PROVIDER=together    # Fast, free tier
```

Or edit the script and change the default:
```python
PROVIDER = os.getenv('AI_PROVIDER', 'ollama').lower()  # Change 'ollama' to your preference
```

---

## Cost Comparison

- **OpenAI GPT-4**: ~$0.03 per 1K tokens → ~$480 for 16K questions
- **Ollama**: $0 (completely free, local)
- **Groq Free Tier**: $0 (generous limits)
- **Gemini Free Tier**: $0 (generous limits)
- **Hugging Face Free**: $0 (rate limited)
- **Together AI Free**: $0 (rate limited)

**Recommendation: Use Ollama for zero cost and no limits!**
