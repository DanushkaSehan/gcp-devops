from flask import Flask, request, render_template, send_from_directory
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing import image
import numpy as np
import os
import cv2
import openai

app = Flask(__name__)
UPLOAD_FOLDER = 'static/uploads/'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Load model
model = load_model("oily_model_final8.h5")

# Set OpenAI key
openai.api_key = os.getenv("OPENAI_API_KEY")

# Helper: preprocess uploaded image
def preprocess_image(image_path):
    img = image.load_img(image_path, target_size=(224, 224))
    img = image.img_to_array(img)
    img = np.expand_dims(img, axis=0)
    return img / 255.0

# Helper: extract skin region
def extract_skin(image_path):
    img = cv2.imread(image_path)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    lower_skin = np.array([0, 48, 80], dtype=np.uint8)
    upper_skin = np.array([20, 255, 255], dtype=np.uint8)
    mask = cv2.inRange(hsv, lower_skin, upper_skin)
    skin = cv2.bitwise_and(img, img, mask=mask)
    
    skin_path = os.path.join(app.config['UPLOAD_FOLDER'], 'skin_' + os.path.basename(image_path))
    cv2.imwrite(skin_path, skin)
    return skin_path

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/predict', methods=['POST'])
def predict():
    if 'file' not in request.files:
        return render_template('index.html', error='No file uploaded.')
    
    file = request.files['file']
    if file.filename == '':
        return render_template('index.html', error='No file selected.')
    
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(file_path)

    # Extract and preprocess
    skin_image_path = extract_skin(file_path)
    processed = preprocess_image(skin_image_path)

    prediction = model.predict(processed)
    predicted_class = np.argmax(prediction)
    class_names = ['non-oily', 'oily']
    label = class_names[predicted_class]
    confidence = prediction[0][predicted_class] * 100

    # Determine oiliness level
    if label == 'oily':
        if confidence > 89:
            level = "HIGH-OILYNESS"
        elif confidence > 70:
            level = "MID-OILYNESS"
        else:
            level = "LOW-OILYNESS"
    else:
        level = "LOW-OILYNESS"

    return render_template('index.html', filename=file.filename, skin_filename=os.path.basename(skin_image_path), confidence_level=confidence, oiliness_level=level)

@app.route('/chatbot', methods=['GET', 'POST'])
def chatbot():
    response = ""
    if request.method == 'POST':
        user_input = request.form.get("user_input")
        try:
            chat = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful skin specialist medical chatbot."},
                    {"role": "user", "content": user_input}
                ]
            )
            response = chat.choices[0].message.content
        except Exception as e:
            response = f"Error: {str(e)}"
    return render_template("bot.html", chat_response=response)

@app.route('/static/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
