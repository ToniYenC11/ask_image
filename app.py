import streamlit as st
import base64
import time
import os
from groq import Groq
from datetime import datetime, timedelta
import json

# Groq API limits for meta-llama/llama-4-scout-17b-16e-instruct
API_LIMITS = {
    "requests_per_minute": 30,
    "requests_per_day": 1000,
    "tokens_per_minute": 30000,
    "tokens_per_day": 500000,
    "per_request_limit": 10000,  # Safe per-request limit
}

def init_session_state():
    """Initialize session state for usage tracking"""
    if 'usage_tracking' not in st.session_state:
        st.session_state.usage_tracking = {
            # Daily tracking
            'daily_tokens': 0,
            'daily_requests': 0,
            'last_daily_reset': datetime.now().strftime('%Y-%m-%d'),
            
            # Minute tracking
            'minute_tokens': 0,
            'minute_requests': 0,
            'last_minute_reset': datetime.now().strftime('%Y-%m-%d %H:%M'),
            
            # Usage history
            'usage_history': []
        }

def reset_usage_counters():
    """Reset usage counters based on time periods"""
    now = datetime.now()
    usage = st.session_state.usage_tracking
    
    # Reset daily counters if new day
    today = now.strftime('%Y-%m-%d')
    if usage['last_daily_reset'] != today:
        usage['daily_tokens'] = 0
        usage['daily_requests'] = 0
        usage['last_daily_reset'] = today
    
    # Reset minute counters if new minute
    current_minute = now.strftime('%Y-%m-%d %H:%M')
    if usage['last_minute_reset'] != current_minute:
        usage['minute_tokens'] = 0
        usage['minute_requests'] = 0
        usage['last_minute_reset'] = current_minute

def check_rate_limits(estimated_tokens=500):
    """Check if request would exceed any rate limits"""
    reset_usage_counters()
    usage = st.session_state.usage_tracking
    
    # Check requests per minute
    if usage['minute_requests'] >= API_LIMITS['requests_per_minute']:
        return False, f"Rate limit exceeded: {API_LIMITS['requests_per_minute']} requests per minute"
    
    # Check requests per day
    if usage['daily_requests'] >= API_LIMITS['requests_per_day']:
        return False, f"Daily limit exceeded: {API_LIMITS['requests_per_day']} requests per day"
    
    # Check tokens per minute
    if usage['minute_tokens'] + estimated_tokens > API_LIMITS['tokens_per_minute']:
        return False, f"Token rate limit exceeded: {API_LIMITS['tokens_per_minute']} tokens per minute"
    
    # Check tokens per day
    if usage['daily_tokens'] + estimated_tokens > API_LIMITS['tokens_per_day']:
        return False, f"Daily token limit exceeded: {API_LIMITS['tokens_per_day']} tokens per day"
    
    # Check per-request limit
    if estimated_tokens > API_LIMITS['per_request_limit']:
        return False, f"Request too large: {estimated_tokens} tokens (max {API_LIMITS['per_request_limit']})"
    
    return True, "OK"

def update_usage_tracking(tokens_used):
    """Update usage tracking with actual token consumption"""
    usage = st.session_state.usage_tracking
    
    # Update counters
    usage['daily_tokens'] += tokens_used
    usage['daily_requests'] += 1
    usage['minute_tokens'] += tokens_used
    usage['minute_requests'] += 1
    
    # Add to history
    usage['usage_history'].append({
        'timestamp': datetime.now().isoformat(),
        'tokens': tokens_used
    })
    
    # Keep only last 50 entries
    if len(usage['usage_history']) > 50:
        usage['usage_history'] = usage['usage_history'][-50:]

def estimate_tokens_from_text(text):
    """Rough estimation of tokens from text (1 token ≈ 4 characters)"""
    return len(text) // 4

def get_groq_client():
    """Get Groq client with API key"""
    try:
        api_key = st.secrets["GROQ_API_KEY"]
        return Groq(api_key=api_key)
    except KeyError:
        st.error("🔑 API key not found. Please configure your Groq API key in Streamlit secrets.")
        return None

def display_usage_stats():
    """Display current API usage statistics"""
    reset_usage_counters()
    usage = st.session_state.usage_tracking
    
    st.sidebar.header("📊 API Usage Stats")
    
    # Per-minute usage
    st.sidebar.subheader("⏱️ Current Minute")
    col1, col2 = st.sidebar.columns(2)
    
    with col1:
        req_min_pct = (usage['minute_requests'] / API_LIMITS['requests_per_minute']) * 100
        st.metric("Requests", f"{usage['minute_requests']}/{API_LIMITS['requests_per_minute']}")
        st.progress(min(req_min_pct / 100, 1.0))
    
    with col2:
        tok_min_pct = (usage['minute_tokens'] / API_LIMITS['tokens_per_minute']) * 100
        st.metric("Tokens", f"{usage['minute_tokens']:,}/{API_LIMITS['tokens_per_minute']:,}")
        st.progress(min(tok_min_pct / 100, 1.0))
    
    # Daily usage
    st.sidebar.subheader("📅 Today")
    col1, col2 = st.sidebar.columns(2)
    
    with col1:
        req_day_pct = (usage['daily_requests'] / API_LIMITS['requests_per_day']) * 100
        st.metric("Requests", f"{usage['daily_requests']}/{API_LIMITS['requests_per_day']}")
        st.progress(min(req_day_pct / 100, 1.0))
    
    with col2:
        tok_day_pct = (usage['daily_tokens'] / API_LIMITS['tokens_per_day']) * 100
        st.metric("Tokens", f"{usage['daily_tokens']:,}/{API_LIMITS['tokens_per_day']:,}")
        st.progress(min(tok_day_pct / 100, 1.0))
    
    # Warnings
    if req_min_pct > 80:
        st.sidebar.warning("⚠️ Approaching per-minute request limit!")
    if tok_min_pct > 80:
        st.sidebar.warning("⚠️ Approaching per-minute token limit!")
    if req_day_pct > 80:
        st.sidebar.warning("⚠️ Approaching daily request limit!")
    if tok_day_pct > 80:
        st.sidebar.warning("⚠️ Approaching daily token limit!")
    
    # Time until reset
    now = datetime.now()
    seconds_until_next_minute = 60 - now.second
    st.sidebar.caption(f"⏳ Minute resets in {seconds_until_next_minute}s")

# Initialize session state
init_session_state()

#* Title of website
st.title("Ask your image")
st.header("Upload your image")

# Display usage stats in sidebar
display_usage_stats()

uploaded_file = st.file_uploader(
    label='Upload an image of your choice (png or jpg). The website will display it and you can then chat with said app.',
    type=['png','jpg','jpeg']
)

#* Display the image immediately after upload
if uploaded_file is not None:
    st.image(uploaded_file, width=300, use_container_width=False)
    st.write("Image uploaded successfully! You can now chat about this image.")

    #* Chat with the image
    st.header("Chat with your image")
    user_question = st.text_input(label="Input your question")

    def generate_caption(uploaded_image, question):
        """Generate caption with token usage tracking"""
        # Estimate tokens for the request
        estimated_tokens = estimate_tokens_from_text(question) + 200  # Add base tokens for image processing
        
        # Check token limits before making request
        can_proceed, message = check_rate_limits(estimated_tokens)
        if not can_proceed:
            return f"❌ Request blocked: {message}"
        
        # Get Groq client
        client = get_groq_client()
        if client is None:
            return "Sorry, the service is temporarily unavailable."
        
        try:
            # Reset file pointer and encode image
            uploaded_image.seek(0)
            base64_image = base64.b64encode(uploaded_image.read()).decode('utf-8')

            # Make API call
            chat_completion = client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": question},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}",
                                },
                            },
                        ],
                    }
                ],
                model="meta-llama/llama-4-scout-17b-16e-instruct",
            )

            # Extract response and token usage
            response_text = chat_completion.choices[0].message.content
            
            # Get actual token usage from the response
            if hasattr(chat_completion, 'usage') and chat_completion.usage:
                total_tokens = chat_completion.usage.total_tokens
                prompt_tokens = chat_completion.usage.prompt_tokens
                completion_tokens = chat_completion.usage.completion_tokens
                
                # Update token usage
                update_usage_tracking(total_tokens)
                
                # Add usage info to response
                response_text += f"\n\n---\n*Token usage: {total_tokens} total ({prompt_tokens} prompt + {completion_tokens} completion)*"
            else:
                # Fallback: estimate tokens from response
                estimated_response_tokens = estimate_tokens_from_text(response_text)
                total_estimated = estimated_tokens + estimated_response_tokens
                update_usage_tracking(total_estimated)
                
                response_text += f"\n\n---\n*Estimated token usage: {total_estimated}*"

            return response_text

        except Exception as e:
            return f"Error generating response: {str(e)}"

    # Only generate response if user has entered a question
    if user_question:
        # Check if we can make the request
        estimated_tokens = estimate_tokens_from_text(user_question) + 200
        can_proceed, message = check_rate_limits(estimated_tokens)
        
        if not can_proceed:
            st.error(f"🚫 {message}")
            st.info("Please try again tomorrow or with a shorter question.")
        else:
            with st.spinner("Analyzing image..."):
                response = generate_caption(uploaded_image=uploaded_file, question=user_question)

            # Create a placeholder for the streaming text
            response_placeholder = st.empty()

            # Simulate typing animation
            displayed_text = ""
            for char in response:
                displayed_text += char
                response_placeholder.markdown(displayed_text)
                time.sleep(0.01)

else:
    st.info("Please upload an image to start chatting!")
    st.header("Chat with your image")
    st.text_input(label="Input your question", disabled=True, placeholder="Upload an image first")

# Add reset button in sidebar for testing
if st.sidebar.button("🔄 Reset Usage (Testing)"):
    st.session_state.usage_tracking = {
        'daily_tokens': 0,
        'daily_requests': 0,
        'last_daily_reset': datetime.now().strftime('%Y-%m-%d'),
        'minute_tokens': 0,
        'minute_requests': 0,
        'last_minute_reset': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'usage_history': []
    }
    st.rerun()

# Display API limits info
with st.sidebar.expander("ℹ️ API Limits Info"):
    st.caption(f"**Requests per minute:** {API_LIMITS['requests_per_minute']}")
    st.caption(f"**Requests per day:** {API_LIMITS['requests_per_day']:,}")
    st.caption(f"**Tokens per minute:** {API_LIMITS['tokens_per_minute']:,}")
    st.caption(f"**Tokens per day:** {API_LIMITS['tokens_per_day']:,}")
    st.caption(f"**Model:** meta-llama/llama-4-scout-17b-16e-instruct")