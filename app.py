from flask import Flask, render_template, request, redirect, url_for, send_from_directory,flash,jsonify
import os
from werkzeug.utils import secure_filename
from pydub import AudioSegment
import tempfile
from flask_sqlalchemy import SQLAlchemy
import re

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = tempfile.mkdtemp()  # Temporary folder for uploaded files
app.config['SPLIT_FOLDER'] = "split"  # Temporary folder for split audio files
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///transcriptions.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = '123456'  # Set the secret key

db = SQLAlchemy(app)

class Transcription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    audio_path = db.Column(db.String(150), nullable=False)
    transcription_text = db.Column(db.Text, nullable=False)


# Create the database and tables
with app.app_context():
    db.create_all()


@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            return redirect(request.url)
        transcription_text = request.form['transcription']  # Extract transcription text
        transcription_segments = parse_transcription(transcription_text) 
        if file:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            split_audio_file(file_path, filename, transcription_text)
            audio_segments = [f for f in os.listdir(app.config['SPLIT_FOLDER']) if f.endswith('.wav') and f != '.DS_Store']
            audio_segments.sort()
            paired_segments = []
            for i, seg in enumerate(audio_segments):
                if i < len(transcription_segments):
                    paired_segments.append({"filename": seg, "transcription": transcription_segments[i]["text"]})
                else:
                    # Handle the case where there's no corresponding transcription segment.
                    # For example, you might want to add a placeholder or skip the segment.
                    paired_segments.append({"filename": seg, "transcription": "No transcription available"})

            return render_template('transcribe.html', segments=paired_segments, folder=app.config['SPLIT_FOLDER'])
    return render_template('upload.html')

def split_audio_file(file_path, filename, transcription):
    sound = AudioSegment.from_mp3(file_path)
    
    # Parse transcription for timestamps and text
    pattern = r"\[(\d+\.\d+)s -> (\d+\.\d+)s\]"
    segments = re.findall(pattern, transcription)

    for i, (start, end) in enumerate(segments):
        start_ms, end_ms = float(start) * 1000, float(end) * 1000  # Convert seconds to milliseconds
        chunk = sound[start_ms:end_ms]
        chunk_name = f"{filename}_chunk{i}.wav"
        chunk_path = os.path.join(app.config['SPLIT_FOLDER'], chunk_name)
        chunk.export(chunk_path, format="wav")

@app.route('/segments/<filename>')
def segment(filename):
    return send_from_directory(app.config['SPLIT_FOLDER'], filename)

@app.route('/save_transcription', methods=['POST'])
def save_transcription():
    transcription = request.form['transcription']
    filename = request.form['filename']
    audio_path = os.path.join(app.config['SPLIT_FOLDER'], filename)

    new_transcription = Transcription(audio_path=audio_path, transcription_text=transcription)
    db.session.add(new_transcription)
    db.session.commit()

    return jsonify({"success": True})

def parse_transcription(transcription):
    # Parses the transcription text to extract timestamps and the text
    pattern = r"\[(\d+\.\d+)s -> (\d+\.\d+)s\]\s+(.+)"
    segments = re.findall(pattern, transcription)
    return [{"start": float(start), "end": float(end), "text": text} for start, end, text in segments]


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)