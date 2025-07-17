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
    
    # Test if we can connect to the database
    try:
        import sqlalchemy
        test_engine = sqlalchemy.create_engine(DATABASE_URL)
        with test_engine.connect() as conn:
            conn.execute(sqlalchemy.text('SELECT 1'))
        app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
        print("✅ Connected to remote PostgreSQL database")
    except Exception as e:
        print(f"❌ Cannot connect to remote database: {e}")
        print("🔄 Falling back to local SQLite database")
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///fallback_csv_data.db'
    
    # Add connection pool settings for better reliability
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_timeout': 20,
        'pool_recycle': 300,
        'pool_pre_ping': True,
        'max_overflow': 0,
    }
else:
    # For local development
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///csv_data.db'
    print("🔧 Using local SQLite database for development")

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Create upload directory if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize database
db = SQLAlchemy(app)

# Database initialization function
def init_database():
    """Initialize database tables"""
    try:
        with app.app_context():
            db.create_all()
            print("✅ Database tables initialized successfully")
            return True
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        return False

# Initialize database on startup
init_database()

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
    upload_record = None
    try:
        # Ensure database is initialized (redundant safety check)
        if not init_database():
            return jsonify({'success': False, 'message': 'Database initialization failed'})
        
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
                
                # Start a new transaction
                try:
                    # Create upload record
                    upload_record = CSVUpload(
                        filename=filename,
                        total_rows=len(df),
                        status='processing'
                    )
                    db.session.add(upload_record)
                    db.session.flush()  # Get the ID without committing
                    
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
                    if os.path.exists(filepath):
                        os.remove(filepath)
                    
                    return jsonify({
                        'success': True, 
                        'message': f'CSV uploaded successfully! {len(df)} rows processed.',
                        'upload_id': upload_record.id,
                        'total_rows': len(df)
                    })
                    
                except Exception as db_error:
                    # Rollback the transaction
                    db.session.rollback()
                    
                    # Try to update status to failed if record exists
                    if upload_record and upload_record.id:
                        try:
                            upload_record.status = 'failed'
                            db.session.add(upload_record)
                            db.session.commit()
                        except:
                            db.session.rollback()
                    
                    # Clean up uploaded file
                    if os.path.exists(filepath):
                        os.remove(filepath)
                    
                    return jsonify({'success': False, 'message': f'Database error: {str(db_error)}'})
                
            except Exception as csv_error:
                # Clean up uploaded file
                if os.path.exists(filepath):
                    os.remove(filepath)
                return jsonify({'success': False, 'message': f'Error processing CSV: {str(csv_error)}'})
        
        else:
            return jsonify({'success': False, 'message': 'Invalid file type. Please upload a CSV file.'})
            
    except Exception as e:
        # Ensure session is rolled back in case of any error
        try:
            db.session.rollback()
        except:
            pass
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
    import sys
    db_info = {}
    try:
        # Get database connection info
        db_uri = app.config['SQLALCHEMY_DATABASE_URI']
        if '@' in db_uri:
            db_info['host'] = db_uri.split('@')[1].split('/')[0]
            db_info['type'] = 'postgresql' if 'postgresql' in db_uri else 'other'
        else:
            db_info['type'] = 'sqlite'
            db_info['file'] = db_uri.replace('sqlite:///', '')
    except:
        db_info['error'] = 'Could not parse database URI'
    
    return jsonify({
        'status': 'Flask app is running on Render',
        'python_version': sys.version,
        'database_url_set': bool(os.environ.get('DATABASE_URL')),
        'database_info': db_info,
        'environment': 'production' if os.environ.get('DATABASE_URL') else 'development',
        'routes': [str(rule) for rule in app.url_map.iter_rules()]
    })

@app.route('/ping')
def ping():
    """Simple ping endpoint that always works"""
    return "pong", 200

@app.route('/status')
def simple_status():
    """Simple status endpoint that doesn't require database"""
    return jsonify({
        'status': 'running',
        'timestamp': datetime.utcnow().isoformat(),
        'environment': 'production' if os.environ.get('DATABASE_URL') else 'development'
    })

@app.route('/health')
def health_check():
    status = {'status': 'healthy', 'components': {}}
    http_status = 200
    
    try:
        # Test database connection
        with db.engine.connect() as connection:
            connection.execute(db.text('SELECT 1'))
        status['components']['database'] = 'connected'
    except Exception as e:
        status['status'] = 'unhealthy'
        status['components']['database'] = f'error: {str(e)}'
        http_status = 500
    
    # Check if we can write to upload folder
    try:
        test_file = os.path.join(app.config['UPLOAD_FOLDER'], 'test.txt')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        status['components']['filesystem'] = 'writable'
    except Exception as e:
        if status['status'] != 'unhealthy':
            status['status'] = 'degraded'
        status['components']['filesystem'] = f'error: {str(e)}'
    
    return jsonify(status), http_status

def startup_health_check():
    """Perform startup health checks"""
    print("🔍 Performing startup health checks...")
    
    # Check 1: Database connection
    try:
        with app.app_context():
            db.engine.connect()
        print("✅ Database connection: OK")
    except Exception as e:
        print(f"⚠️ Database connection: DEGRADED ({e})")
    
    # Check 2: Upload folder
    try:
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        test_file = os.path.join(app.config['UPLOAD_FOLDER'], 'startup_test.txt')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        print("✅ Upload folder: OK")
    except Exception as e:
        print(f"❌ Upload folder: ERROR ({e})")
    
    # Check 3: Template folder
    try:
        template_path = os.path.join(app.template_folder, 'index.html')
        if os.path.exists(template_path):
            print("✅ Templates: OK")
        else:
            print("⚠️ Templates: index.html not found")
    except Exception as e:
        print(f"❌ Templates: ERROR ({e})")
    
    print("🚀 Startup health checks completed")

# Run startup checks
startup_health_check()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    
    # Get port from environment variable (Render sets this)
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
