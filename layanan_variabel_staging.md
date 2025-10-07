# ENVOYOU SEC API (STAGING)

## rincian lengkap layanan dan variabel yang kita gunakan untuk lingkungan *staging*.

---
### 1. Server (VPS - Virtual Private Server)
* **Penyedia**: **DigitalOcean**
* **Layanan**: Droplet (Virtual Machine)
* **Variabel Terkait**:
    * `STAGING_HOST`: **Alamat IP** dari Droplet.
    * `STAGING_USER`: **Username** untuk login ke server. ini adalah `root`.
    * `STAGING_SSH_KEY`: **Kunci privat SSH**. Digunakan oleh GitHub Actions untuk login ke server tanpa password.

---
### 2. Database Utama
* **Penyedia**: **Supabase**
* **Layanan**: Managed PostgreSQL Database
* **Variabel Terkait**:
    * `STAGING_DATABASE_URL`: **URL koneksi lengkap**.

---
### 3. Cache
Penyimpanan data sementara super cepat untuk mempercepat aplikasi.
* **Penyedia**: Eksternal/Managed (**Upstash**)
* **Layanan**: Managed Redis
* **Variabel Terkait**:
    * `STAGING_REDIS_URL`: **URL koneksi lengkap**.

---
### 4. Keamanan Aplikasi
Kunci rahasia internal yang digunakan oleh aplikasi FastAPI Anda.
* **Penyedia**: Saya Buat Sendiri
* **Variabel Terkait**:
    * `STAGING_SECRET_KEY`: **Kunci rahasia acak** untuk mengamankan sesi dan token.
    * `STAGING_JWT_ALGORITHM`: **Algoritma** (`HS256`) yang dipilih untuk keamanan JSON Web Token.

---
### 5. Monitoring
Layanan untuk memantau kesehatan dan performa aplikasi, berjalan di dalam Docker di VPS.
* **Penyedia**: Self-Hosted.
* **Layanan**: **Grafana** & **Prometheus**
* **Variabel Terkait**:
    * `GRAFANA_ADMIN_PASSWORD`: **Password** yang Saya buat sendiri untuk login ke dashboard Grafana dengan username `admin`.

---
### 6. Notifikasi Deployment
Layanan untuk mengirim pemberitahuan status deployment Anda.
* **Penyedia**: **Slack**
* **Layanan**: Incoming Webhook
* **Variabel Terkait**:
    * `SLACK_WEBHOOK_URL`: **URL unik** yang didapat dari halaman konfigurasi Aplikasi Slack untuk mengirim pesan ke channel tertentu.

---
### 7. Container Registry
Tempat menyimpan "paket jadi" (image) dari aplikasi.
* **Penyedia**: **Docker Hub**
* **Layanan**: Docker Image Registry
* **Variabel Terkait**:
    * `DOCKER_USERNAME`: **Username**.
    * `DOCKER_PASSWORD`: **Personal Access Token** dari Docker Hub (bukan password akun).

## Ringkasan Tabel Variabel

| Variabel | Kegunaan | Sumber / Dibuat di |
| :--- | :--- | :--- |
| `STAGING_HOST` | Alamat IP Server | DigitalOcean |
| `STAGING_USER` | Username Server | DigitalOcean (default: `root`) |
| `STAGING_SSH_KEY` | Kunci Privat untuk Login | Saya Buat Sendiri (Lokal) |
| `STAGING_DATABASE_URL` | URL Koneksi ke Database | Supabase |
| `STAGING_REDIS_URL` | URL Koneksi ke Cache Redis | Penyedia Redis (Upstash) |
| `STAGING_SECRET_KEY` | Kunci Rahasia Aplikasi | Saya Buat Sendiri (Acak) |
| `STAGING_JWT_ALGORITHM`| Algoritma Keamanan Token | Saya Tentukan Sendiri (`HS256`) |
| `GRAFANA_ADMIN_PASSWORD` | Password Login Grafana | Saya Buat Sendiri |
| `SLACK_WEBHOOK_URL` | Alamat Notifikasi Deployment | Slack |
| `DOCKER_USERNAME` | Username Registry Image | Docker Hub |
| `DOCKER_PASSWORD` | Token Registry Image | Docker Hub |
| `STAGING_CORS_ORIGINS` | Izin Akses untuk Frontend | Saya Tentukan Sendiri |
| `EPA_API_KEY` | Kunci untuk API Eksternal | Environmental Protection Agency |
