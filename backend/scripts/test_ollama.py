#!/usr/bin/env python3
"""
Quick test to verify Ollama is working with the expert answers script.
"""
import requests
import json

def test_ollama():
    """Test if Ollama is accessible and working"""
    base_url = "http://localhost:11434"
    models = []  # Initialize models list
    
    print("Testing Ollama connection...")
    
    # Test 1: Check if server is running
    try:
        response = requests.get(f"{base_url}/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get('models', [])
            print(f"✓ Ollama server is running")
            print(f"✓ Found {len(models)} installed model(s):")
            for model in models[:5]:  # Show first 5
                print(f"  - {model.get('name', 'unknown')}")
            if len(models) == 0:
                print("\n⚠️  No models installed!")
                print("   Install a model with: ollama pull llama3.2")
                return False
        else:
            print(f"✗ Ollama server returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("✗ Cannot connect to Ollama server")
        print("   Make sure 'ollama serve' is running")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False
    
    # Test 2: Try a simple generation
    print("\nTesting model generation...")
    test_model = "llama3.2"  # Default model
    
    # Check if we have any model - use FULL name including tag (e.g., "llama3.1:8b")
    if models:
        test_model = models[0].get('name', 'llama3.2')  # Use full name
        print(f"  Using model: {test_model}")
    
    try:
        payload = {
            "model": test_model,
            "prompt": "Answer with just the number 4",
            "stream": False,
            "options": {
                "temperature": 0.7,
                "num_predict": 10
            }
        }
        
        response = requests.post(f"{base_url}/api/generate", json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        answer = result.get('response', '').strip()
        
        print(f"✓ Model '{test_model}' is working!")
        print(f"  Test response: {answer[:50]}")
        return True
        
    except Exception as e:
        print(f"✗ Model generation failed: {e}")
        print(f"  Make sure model '{test_model}' is installed:")
        print(f"  ollama pull {test_model}")
        return False


if __name__ == '__main__':
    print("="*60)
    print("Ollama Connection Test")
    print("="*60)
    print()
    
    success = test_ollama()
    
    print()
    print("="*60)
    if success:
        print("✓ All tests passed! Ollama is ready to use.")
        print("\nYou can now run:")
        print("  export AI_PROVIDER=ollama")
        print("  python3 generate_expert_answers_free.py")
    else:
        print("✗ Tests failed. Please fix the issues above.")
    print("="*60)
