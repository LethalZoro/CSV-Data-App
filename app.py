from flask import Flask, request, render_template, jsonify, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
import pandas as pd
import os
from datetime import datetime
from dotenv import load_dotenv
import json
import csv
import io
import sys

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev-key-change-in-production')

# Enhanced database configuration for Render
DATABASE_URL = os.getenv('DATABASE_URL')
if DATABASE_URL:
    # For production (Render provides PostgreSQL URLs)
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://')
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
else:
    # For local development
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///csv_data.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Create upload directory if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize database
db = SQLAlchemy(app)

# Database Models
class CSVUpload(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    total_rows = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(50), default='uploaded')
    
    def to_dict(self):
        return {
            'id': self.id,
            'filename': self.filename,
            'upload_date': self.upload_date.isoformat(),
            'total_rows': self.total_rows,
            'status': self.status
        }

class CSVData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    upload_id = db.Column(db.Integer, db.ForeignKey('csv_upload.id'), nullable=False)
    row_data = db.Column(db.Text, nullable=False)  # JSON string of the row data
    row_number = db.Column(db.Integer, nullable=False)
    
    upload = db.relationship('CSVUpload', backref=db.backref('data_rows', lazy=True))
    
    def to_dict(self):
        return {
            'id': self.id,
            'upload_id': self.upload_id,
            'row_data': json.loads(self.row_data),
            'row_number': self.row_number
        }

# Allowed file extensions
ALLOWED_EXTENSIONS = {'csv'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'No file selected'})
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'message': 'No file selected'})
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Parse CSV and store in database
            try:
                df = pd.read_csv(filepath)
                
                # Create upload record
                upload_record = CSVUpload(
                    filename=filename,
                    total_rows=len(df),
                    status='processing'
                )
                db.session.add(upload_record)
                db.session.commit()
                
                # Store each row in the database
                for index, row in df.iterrows():
                    row_data = CSVData(
                        upload_id=upload_record.id,
                        row_data=json.dumps(row.to_dict()),
                        row_number=index + 1
                    )
                    db.session.add(row_data)
                
                # Update status to completed
                upload_record.status = 'completed'
                db.session.commit()
                
                # Clean up uploaded file
                os.remove(filepath)
                
                return jsonify({
                    'success': True, 
                    'message': f'CSV uploaded successfully! {len(df)} rows processed.',
                    'upload_id': upload_record.id,
                    'total_rows': len(df)
                })
                
            except Exception as e:
                # Update status to failed
                if 'upload_record' in locals():
                    upload_record.status = 'failed'
                    db.session.commit()
                
                return jsonify({'success': False, 'message': f'Error processing CSV: {str(e)}'})
        
        else:
            return jsonify({'success': False, 'message': 'Invalid file type. Please upload a CSV file.'})
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'Upload failed: {str(e)}'})

@app.route('/uploads')
def get_uploads():
    try:
        uploads = CSVUpload.query.order_by(CSVUpload.upload_date.desc()).all()
        return jsonify({
            'success': True,
            'uploads': [upload.to_dict() for upload in uploads]
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error fetching uploads: {str(e)}'})

@app.route('/upload/<int:upload_id>/data')
def get_upload_data(upload_id):
    try:
        upload = CSVUpload.query.get_or_404(upload_id)
        data_rows = CSVData.query.filter_by(upload_id=upload_id).order_by(CSVData.row_number).all()
        
        return jsonify({
            'success': True,
            'upload': upload.to_dict(),
            'data': [row.to_dict() for row in data_rows]
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error fetching data: {str(e)}'})

@app.route('/debug')
def debug_info():
    """Debug endpoint to check deployment status"""
    return jsonify({
        'status': 'Flask app is running on Render',
        'python_version': sys.version,
        'database_url_set': bool(os.environ.get('DATABASE_URL')),
        'environment': 'production' if os.environ.get('DATABASE_URL') else 'development',
        'routes': [str(rule) for rule in app.url_map.iter_rules()]
    })

@app.route('/health')
def health_check():
    try:
        # Test database connection
        db.session.execute('SELECT 1')
        return jsonify({'status': 'healthy', 'database': 'connected'})
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    
    # Get port from environment variable (Render sets this)
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
