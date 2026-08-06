# ☁️ Cloud File Management & Monitoring Dashboard

A professional, full-stack Cloud Engineering project built with Python Flask, AWS S3, and vanilla JavaScript. 

This project demonstrates core cloud concepts including object storage integration, server-side monitoring, RESTful APIs, and secure authentication.

---

## 📋 Table of Contents
1. [Project Overview](#project-overview)
2. [Features](#features)
3. [Technologies Used](#technologies-used)
4. [Architecture](#architecture)
5. [Folder Structure](#folder-structure)
6. [Local Setup Instructions](#local-setup-instructions)
7. [AWS Setup Guide](#aws-setup-guide)
8. [Deployment Guide (EC2 & Nginx)](#deployment-guide)
9. [Testing the APIs](#testing-the-apis)
10. [CloudWatch Monitoring](#cloudwatch-monitoring)
11. [Common Errors and Solutions](#common-errors-and-solutions)
12. [Interview Preparation](#interview-preparation)

---

## 🎯 Project Overview

This dashboard allows users to register, log in, and securely upload files to the cloud (AWS S3). It includes a real-time server monitoring dashboard that tracks CPU, memory, and disk usage, making it an ideal portfolio project for a Cloud Engineering internship.

It is designed to work completely locally using SQLite and local file storage, with seamless configuration to switch to PostgreSQL and AWS S3 for production.

---

## ✨ Features

- **Authentication**: Secure registration and login with Werkzeug password hashing.
- **File Management**: Upload, list, download, and delete files; choose Local or Amazon S3 for each upload.
- **Monitoring Dashboard**: Real-time system metrics (CPU, RAM, Disk) using `psutil`.
- **Responsive UI**: Glassmorphism design with a dark cloud theme, completely built without heavy frontend frameworks (vanilla JS & CSS).
- **RESTful API**: Clean JSON endpoints for easy integration with mobile or other clients.

---

## 🛠 Technologies Used

- **Frontend**: HTML5, CSS3 (Custom Design System), Vanilla JavaScript (`fetch` API)
- **Backend**: Python 3.10+, Flask, Flask-Login, SQLAlchemy
- **Database**: SQLite (Local) -> PostgreSQL (Production ready)
- **Cloud (AWS)**: Amazon S3 (Storage), EC2 (Compute), IAM (Security), CloudWatch (Monitoring)
- **Server**: Gunicorn (WSGI), Nginx (Reverse Proxy)
- **System Metrics**: `psutil` (Python library)

---

## 🏗 Architecture

```text
User Browser
    │ (HTTPS / port 443)
    ▼
Nginx (Reverse Proxy)
    │ (localhost:5000)
    ▼
Gunicorn WSGI Server
    │
    ▼
Flask REST API ────────────────────┐
    │                              │
    ▼                              ▼
AWS S3 Bucket                 SQLite / PostgreSQL
(File Storage)                (User & File Metadata)
    ▲
    │
AWS EC2 Instance
    │
    ▼
AWS CloudWatch (Logs & Metrics)
```

---

## 📂 Folder Structure

```text
cloud-file-dashboard/
│
├── app.py                      # Flask application factory
├── config.py                   # Configuration settings (Dev/Prod)
├── requirements.txt            # Python dependencies
├── .env.example                # Environment variables template
├── .gitignore
├── README.md
│
├── routes/                     # Application Blueprints
│   ├── auth.py                 # Login, Register, Session management
│   ├── files.py                # Upload, Download, Delete APIs
│   └── monitoring.py           # Health checks and system metrics
│
├── services/                   # Business Logic
│   ├── s3_service.py           # Boto3 AWS S3 integration
│   └── monitoring_service.py   # Psutil server metrics collection
│
├── database/                   # Database Models
│   └── models.py               # SQLAlchemy classes (User, FileRecord)
│
├── templates/                  # Frontend HTML Views (Jinja2)
│   ├── index.html              # Landing page
│   ├── login.html
│   ├── register.html
│   └── dashboard.html          # Main application shell (SPA-like)
│
├── static/                     # Frontend Assets
│   ├── css/style.css
│   └── js/app.js               # Vanilla JS API integration
│
└── uploads/                    # Local storage fallback directory
```

---

## 💻 Local Setup Instructions

Follow these steps to run the project on your local machine.

### 1. Python Virtual Environment Setup

Open your terminal and clone the repository (if on GitHub), then navigate to the folder:

```bash
cd cloud-file-dashboard

# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 2. Installing Dependencies

```bash
pip install -r requirements.txt
```

### 3. Environment Variable Configuration

```bash
# Copy the template to create your .env file
cp .env.example .env
```
Set `SECRET_KEY` to a random value. To use S3, set `S3_BUCKET_NAME` and `AWS_REGION` in `.env`, then provide AWS credentials through an AWS CLI profile (`aws configure`), environment variables, or an attached IAM role. Leave `S3_BUCKET_NAME` empty to use local storage. Never commit AWS credentials.

### 4. Database Setup

The application uses SQLite by default. The database tables are automatically created the first time the app runs.

### 5. Running the Flask Application

```bash
python app.py
```
Open your browser and navigate to `http://localhost:5000`.

---

## ☁️ AWS Setup Guide

To switch from local storage to Amazon S3:

### 1. S3 Bucket Creation
1. Go to AWS Console > **S3** > **Create bucket**.
2. Name it uniquely (e.g., `myname-cloud-dashboard-2024`).
3. Keep **Block all public access** enabled (we use pre-signed URLs for secure downloads).
4. Create the bucket.

### 2. IAM Permissions
For local development, create an IAM user:
1. AWS Console > **IAM** > **Users** > **Create User**.
2. Name it `cloud-dashboard-app`.
3. Attach policies directly > **Create Policy**. Use this JSON:
   ```json
   {
       "Version": "2012-10-17",
       "Statement": [
           {
               "Effect": "Allow",
               "Action": ["s3:PutObject", "s3:GetObject", "s3:DeleteObject", "s3:ListBucket"],
               "Resource": [
                   "arn:aws:s3:::YOUR-BUCKET-NAME",
                   "arn:aws:s3:::YOUR-BUCKET-NAME/*"
               ]
           }
       ]
   }
   ```
4. Generate **Access Keys** for this user.

Set `S3_BUCKET_NAME` and `AWS_REGION` in `.env`. For local development, provide the IAM user's access keys as `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`, or use an AWS CLI profile (`aws configure`). On EC2, attach an IAM role with the bucket permissions instead of storing access keys. Restart Flask; the dashboard's S3 indicator verifies bucket access using `s3:ListBucket`.

---

## 🚀 Deploying to AWS EC2

### 1. Configuring the EC2 Server
1. Launch an EC2 Instance (Ubuntu 22.04 LTS, t2.micro).
2. Create an **IAM Role** for EC2 and attach the S3 policy created above. Assign this role to your EC2 instance (this replaces the need for `.env` AWS keys!).
3. Configure Security Group: Allow inbound HTTP (80), HTTPS (443), and SSH (22).

### 2. Installing Python and Dependencies on EC2
SSH into your server and run:
```bash
sudo apt update
sudo apt install python3-pip python3-venv nginx -y

# Clone your code (or use SCP/SFTP)
git clone <your-repo-url>
cd cloud-file-dashboard

# Setup env
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Running Flask with Gunicorn
We use Gunicorn instead of the Flask development server for production.
```bash
# Test gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 "app:create_app()"
```

To keep it running in the background, create a systemd service:
```bash
sudo nano /etc/systemd/system/clouddash.service
```
```ini
[Unit]
Description=Gunicorn instance to serve CloudDash
After=network.target

[Service]
User=ubuntu
Group=www-data
WorkingDirectory=/home/ubuntu/cloud-file-dashboard
Environment="PATH=/home/ubuntu/cloud-file-dashboard/venv/bin"
Environment="FLASK_ENV=production"
ExecStart=/home/ubuntu/cloud-file-dashboard/venv/bin/gunicorn -w 4 -b 127.0.0.1:5000 "app:create_app()"

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl start clouddash
sudo systemctl enable clouddash
```

### 4. Configuring Nginx
```bash
sudo nano /etc/nginx/sites-available/clouddash
```
```nginx
server {
    listen 80;
    server_name your_domain_or_IP;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        
        # Allow large file uploads
        client_max_body_size 50M;
    }
}
```
```bash
sudo ln -s /etc/nginx/sites-available/clouddash /etc/nginx/sites-enabled
sudo nginx -t
sudo systemctl restart nginx
```

---

## 🧪 Testing the APIs

You can test the APIs using cURL or Postman.

**Health Check:**
```bash
curl http://localhost:5000/api/health
```

**Metrics (Requires Authentication Session):**
```bash
curl -b cookies.txt http://localhost:5000/api/metrics
```

---

## 📈 CloudWatch Monitoring

To monitor your EC2 instance at a granular level:
1. Install the CloudWatch Agent on your EC2 instance.
2. What to monitor:
   - **DiskSpaceUtilization**: Ensure your server doesn't run out of space.
   - **CPUUtilization**: Trigger an alarm if CPU > 80% for 5 minutes.
   - **MemoryUtilization**: Track RAM usage (custom metric via CW Agent).
3. **Application Logs**: Configure the CloudWatch agent to push Nginx (`/var/log/nginx/error.log`) and Gunicorn logs to CloudWatch Logs for centralized debugging.

---

## 🐛 Common Errors and Solutions

- **`ModuleNotFoundError: No module named 'flask'`**: You forgot to activate your virtual environment. Run `source venv/bin/activate` (Linux/Mac) or `venv\Scripts\activate` (Windows).
- **`botocore.exceptions.NoCredentialsError`**: S3 is enabled but AWS credentials are not found. Check your `.env` file or EC2 IAM Role.
- **`413 Request Entity Too Large`**: You are uploading a file > 50MB. If on Nginx, ensure `client_max_body_size 50M;` is set.
- **Database Locked**: SQLite handles one writer at a time. If testing heavy concurrency, migrate to PostgreSQL.

---

## 🎓 Interview Preparation

### How to Explain This Project

**1-Minute Pitch:**
> "For my portfolio, I built a Cloud File Management Dashboard using Python, Flask, and AWS S3. It allows users to securely register, log in, and upload files to the cloud. I implemented a real-time server monitoring dashboard using Python's `psutil` to track CPU, memory, and disk usage. The backend is deployed on an AWS EC2 instance using Gunicorn and Nginx as a reverse proxy, and it uses IAM roles for secure, credential-less S3 access."

**3-Minute Detailed Pitch:**
> "I developed a full-stack Cloud File Dashboard to solidify my understanding of cloud infrastructure and backend development. 
> 
> For the architecture, I used Flask for the REST API and SQLite for metadata, structuring it with SQLAlchemy so it can easily migrate to PostgreSQL. The frontend is built without frameworks, using vanilla JavaScript and CSS glassmorphism, communicating asynchronously via the `fetch` API.
>
> A key feature is the storage layer. Files are securely uploaded to an AWS S3 bucket. I intentionally kept the bucket private and used boto3 to generate temporary pre-signed URLs for downloads, ensuring security. 
>
> I also built a real-time monitoring panel. The Flask backend queries the host system using `psutil` to stream CPU, RAM, and disk metrics to the frontend.
>
> Finally, for deployment, I set up an Ubuntu EC2 instance. I configured Nginx as a reverse proxy to route traffic to a Gunicorn WSGI server. For AWS security, I didn't hardcode any access keys; instead, I attached an IAM Instance Role to the EC2 server following the principle of least privilege."

### Q&A Section

#### Beginner Questions
1. **What does Flask do in this project?**
   - It acts as the backend web framework, handling routing, API endpoints, and database interactions.
2. **Why use a virtual environment?**
   - It isolates the project's dependencies (like boto3 and Flask) so they don't conflict with other Python projects on the system.
3. **What is an API?**
   - Application Programming Interface. In this project, it's the URL endpoints that the frontend JavaScript calls to get or send JSON data.
4. **Where are the uploaded files actually stored?**
   - Choose Local or Amazon S3 in the File Manager before uploading. Local files are stored under `uploads/`; S3 uploads require a configured bucket. Metadata (like the file name and size) is stored in the database.
5. **What is environment variables (`.env`) used for?**
   - To securely store configuration like Secret Keys and DB URLs outside of the source code.
6. **Why do we hash passwords?**
   - So if the database is compromised, the attackers only see random characters (hashes), not the users' actual passwords.
7. **What does `requirements.txt` do?**
   - It lists all the Python packages needed to run the project. `pip install -r` reads it.
8. **What is JSON?**
   - JavaScript Object Notation. It's a standard text format for data exchange used between our frontend and Flask APIs.
9. **Why use an IAM user instead of the AWS root account?**
   - Security. The root account has unlimited power. An IAM user can be restricted to only access specific S3 buckets.
10. **What is localhost?**
    - It's a hostname that refers to your own computer (IP 127.0.0.1). 

#### Intermediate Questions
1. **Why did you use pre-signed URLs instead of making the S3 bucket public?**
   - Security. Making the bucket public means anyone can download the files. Pre-signed URLs grant temporary access only to authenticated users who click "Download".
2. **How does the frontend communicate with the backend?**
   - Through asynchronous HTTP requests using the vanilla JavaScript `fetch()` API.
3. **What is a reverse proxy, and why use Nginx?**
   - Nginx sits in front of the application. It handles incoming HTTP connections, manages SSL certificates, serves static files efficiently, and proxies the API requests to Gunicorn.
4. **What is the difference between Authentication and Authorization?**
   - Authentication verifies *who* you are (login). Authorization verifies *what* you can do (e.g., you can only delete your own files).
5. **Why use Gunicorn instead of Flask's built-in server?**
   - Flask's built-in server is single-threaded and not secure/scalable for production. Gunicorn is a robust WSGI HTTP server that can handle concurrent requests using worker processes.
6. **How would you migrate this from SQLite to PostgreSQL?**
   - Since I used SQLAlchemy (an ORM), I only need to change the `DATABASE_URL` environment variable and install a driver like `psycopg2`. No SQL queries need to be rewritten.
7. **How does session management work in this app?**
   - Flask-Login uses a secure, signed cookie stored in the user's browser. On every request, Flask reads the cookie, verifies the signature using the `SECRET_KEY`, and identifies the user.
8. **What is a soft delete?**
   - Instead of deleting a file record from the database, we set an `is_deleted = True` flag. (The physical file is still deleted from S3 to save space).
9. **Why did you structure the Flask app using Blueprints?**
   - To keep the code modular. It separates auth logic, file logic, and monitoring logic into different files rather than having one massive `app.py`.
10. **What is the purpose of the `/api/health` endpoint?**
    - It allows load balancers (like AWS ALB) or uptime monitors to constantly ping the app and verify it is running and can connect to the database.

#### AWS Specific Questions
1. **What is Amazon S3?**
   - Simple Storage Service. An object storage service offering high scalability, data availability, and security.
2. **What is an IAM Role and how does it differ from an IAM User?**
   - A user represents a person or app with long-term credentials (Access Keys). A Role is assumable by a service (like EC2) and provides temporary, rotating credentials.
3. **Why is it a bad idea to put AWS Access Keys in GitHub?**
   - Bots constantly scan GitHub for exposed keys. If found, attackers will use them to spin up expensive infrastructure (like crypto miners) on your account.
4. **What is EC2?**
   - Elastic Compute Cloud. It provides scalable virtual servers in the cloud.
5. **If the EC2 instance reboots, what happens to the app?**
   - Because we configured a `systemd` service for Gunicorn, the OS will automatically restart the application when the server boots.
6. **How do Security Groups work?**
   - They act as a virtual firewall for the EC2 instance, controlling inbound and outbound traffic at the port level.
7. **What is AWS CloudWatch?**
   - A monitoring and observability service. It collects logs, metrics, and events from AWS resources.
8. **How would you scale this application?**
   - Place an Application Load Balancer (ALB) in front of an Auto Scaling Group of EC2 instances. Change the database to Amazon RDS (PostgreSQL). S3 already scales infinitely.
9. **What are S3 Buckets globally unique?**
   - Yes, the bucket name must be unique across all AWS accounts worldwide because it forms part of the public URL.
10. **How does the `boto3` library find credentials on EC2 if they aren't in `.env`?**
    - Boto3 checks an internal metadata endpoint (`169.254.169.254`) that AWS provides to all EC2 instances to retrieve temporary credentials from the attached IAM role.

#### Resume Action Verbs to Use
- **Architected** a scalable file management system.
- **Implemented** secure object storage using AWS S3.
- **Deployed** a Python backend to EC2 using Gunicorn and Nginx.
- **Engineered** a real-time monitoring dashboard utilizing `psutil`.
- **Secured** cloud infrastructure via IAM least-privilege roles.
