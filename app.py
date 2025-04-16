from flask import Flask, render_template, request, redirect, url_for, send_file
import os
import uuid
import base64
from werkzeug.utils import secure_filename
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image
from dotenv import load_dotenv

# 🔐 .env 파일에서 비밀키 불러오기
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "default_secret_key")

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

child_data = {}
handover_logs = {}

# 한글 폰트 등록 (batang.ttc 사용)
pdfmetrics.registerFont(TTFont('Batang', 'fonts/batang.ttc'))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_and_resize_image(file):
    if file and allowed_file(file.filename):
        filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        try:
            img = Image.open(filepath)
            img.thumbnail((300, 300))
            img.save(filepath)
        except Exception as e:
            print("이미지 처리 오류:", e)
        return filename
    return None

@app.route('/')
def home():
    return redirect(url_for('register'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        guardians = []
        for i in range(1, 6):
            name = request.form.get(f'name{i}')
            phone = request.form.get(f'phone{i}')
            file = request.files.get(f'photo{i}')
            filename = save_and_resize_image(file)
            if name and phone:
                guardians.append({
                    'name': name,
                    'phone': phone,
                    'photo': filename
                })

        child_id = str(uuid.uuid4())[:8]
        child_data[child_id] = guardians
        handover_logs[child_id] = []

        return redirect(url_for('child_page', child_id=child_id))

    return render_template('register.html')

@app.route('/child/<child_id>')
def child_page(child_id):
    guardians = child_data.get(child_id, [])
    return render_template('child.html', guardians=guardians, child_id=child_id)

@app.route('/handover/<child_id>', methods=['GET', 'POST'])
def handover(child_id):
    if request.method == 'POST':
        name = request.form['name']
        signature_data = request.form['signature']

        header, encoded = signature_data.split(",", 1)
        data = base64.b64decode(encoded)
        filename = f"{uuid.uuid4().hex}_signature.png"
        filepath = os.path.join('static/uploads', filename)
        with open(filepath, 'wb') as f:
            f.write(data)

        handover_logs[child_id].append({'name': name, 'signature_file': filename})
        return "인도 완료! 감사합니다 😊"

    return render_template('handover.html', guardians=child_data[child_id])

@app.route('/edit/<child_id>', methods=['GET', 'POST'])
def edit_guardians(child_id):
    guardians = child_data.get(child_id, [])

    if request.method == 'POST':
        updated_guardians = []
        for i in range(1, 6):
            name = request.form.get(f'name{i}')
            phone = request.form.get(f'phone{i}')
            file = request.files.get(f'photo{i}')
            filename = request.form.get(f'existing_photo{i}')

            if file and allowed_file(file.filename):
                filename = save_and_resize_image(file)

            delete = request.form.get(f'delete{i}')
            if delete == 'on':
                continue

            if name and phone:
                updated_guardians.append({
                    'name': name,
                    'phone': phone,
                    'photo': filename
                })

        child_data[child_id] = updated_guardians
        return redirect(url_for('child_page', child_id=child_id))

    return render_template('edit.html', guardians=guardians, child_id=child_id)

@app.route('/export_pdf/<child_id>')
def export_pdf(child_id):
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    pdfmetrics.registerFont(TTFont('Batang', 'fonts/batang.ttc'))

    logs = handover_logs.get(child_id, [])
    buffer = BytesIO()
    p = canvas.Canvas(buffer)
    p.setFont("Batang", 12)

    p.drawString(100, 800, f"인도 기록 - Child ID: {child_id}")

    y = 760
    for log in logs:
        p.drawString(100, y, f"보호자: {log['name']}")

        # 서명 이미지 경로 가져오기
        img_path = os.path.join('static', 'uploads', log['signature_file'])

        # 이미지가 존재하면 PDF에 추가
        if os.path.exists(img_path):
            p.drawImage(img_path, 100, y - 60, width=150, height=50)

        y -= 120  # 줄 간격 띄우기

    p.showPage()
    p.save()
    buffer.seek(0)

    return send_file(buffer, as_attachment=True, download_name=f"handover_{child_id}.pdf", mimetype='application/pdf')
