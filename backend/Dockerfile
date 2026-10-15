FROM python:3.11-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY index.html mobile.html config.js ./
EXPOSE 8300
ENV VMS_DB=/srv/data/vms.db
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8300"]
