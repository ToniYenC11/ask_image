import streamlit as st
from groq import Groq
import base64
import os
import json
import time

#* Title of website
st.title("Ask your image")
st.header("Upload your image")

uploaded_file = st.file_uploader(
    label='Upload an image of your choice (png or jpg). The website will display it and you can then chat with said app.',
    type=['png','jpg','jpeg']
)

#* Display the image immediately after upload
if uploaded_file is not None:
    st.image(uploaded_file, width=300, use_container_width=False)
    
    # Optional: Add some spacing or additional functionality
    st.write("Image uploaded successfully! You can now chat about this image.")

    #* Chat with the image
    st.header("Chat with your image")
    user_question = st.text_input(label="Input your question")

    #* generate answer
    def generate_caption(uploaded_image, question):
        # Reset file pointer to beginning
        uploaded_image.seek(0)
        
        # Encode the uploaded image to base64
        base64_image = base64.b64encode(uploaded_image.read()).decode('utf-8')

        # Initialize the Groq client
        client = Groq()

        # Create the chat completion request
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
            model="meta-llama/llama-4-scout-17b-16e-instruct",  # Replace with the correct model name if needed
        )

        # Return the generated caption
        return chat_completion.choices[0].message.content

    # Only generate response if user has entered a question
    if user_question:
        try:
            response = generate_caption(uploaded_image=uploaded_file, question=user_question)

            # Create a placeholder for the streaming text
            response_placeholder = st.empty()

            # Simulate typing animation
            displayed_text = ""
            for char in response:
                displayed_text += char
                response_placeholder.markdown(displayed_text)
                time.sleep(0.01)  # Adjust speed here (lower = faster)
                
        except Exception as e:
            st.error(f"Error generating response: {str(e)}")

else:
    st.info("Please upload an image to start chatting!")
    
    # Show the chat section but disable it
    st.header("Chat with your image")
    st.text_input(label="Input your question", disabled=True, placeholder="Upload an image first")