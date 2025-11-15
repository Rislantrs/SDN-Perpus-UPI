# 📘 **README – Simulasi Jaringan Perpustakaan UPI Purwakarta Menggunakan Mininet-WiFi + Ryu**

## 📌 **1. Deskripsi Umum Proyek**

Project ini mensimulasikan **topologi jaringan perpustakaan UPI Purwakarta** menggunakan:

* **Mininet-WiFi** (versi terbaru, pada Ubuntu 20.04)
* **Ryu SDN Controller** (Ubuntu 24.04, menggunakan Python 3.9 + virtual environment)
* **OVS + Queue QoS** untuk memberi *prioritas trafik*
* Model WiFi fisik dalam ruangan berukuran 50 m × 50 m
* **5 skenario pengujian QoS**:
  Latency, Throughput, Packet Loss

Tujuan proyek ini adalah:

1. Mendesain topologi **hybrid** (kabel + WiFi) yang realistis seperti lingkungan perpustakaan.
2. Mengukur dampak **jumlah pengunjung (STA)** terhadap kualitas jaringan.
3. Menguji **prioritas trafik** untuk layanan penting (host `h_buku`).
4. Membandingkan **hasil eksperimen pertama dan kedua** untuk melihat konsistensi performa.

---

## 📌 **2. Tools & Environment**

### **Mininet-WiFi (Ubuntu 20.04)**

Karena versi Mininet-WiFi baru tidak memiliki installer lengkap, banyak dependency harus di-*clone* dan di-compile manual:

* `wireless-tools`
* `wmediumd`
* patching OVS event
* Python modules Mininet WiFi

### **Ryu Controller (Ubuntu 24.04)**

Menggunakan:

```bash
sudo apt install python3.9 python3.9-venv
python3.9 -m venv ryu
source ryu/bin/activate
pip install ryu
```

Alasan memakai Ubuntu 24:

* Python terbaru (3.9–3.11)
* Ditargetkan untuk kestabilan script OpenFlow 1.3
* Lebih kompatibel dengan Mininet-WiFi modern

---

## 📌 **3. Topologi Hybrid Perpustakaan**

```
        ┌──────────────┐
        │   RYU CTRL   │
        └───────┬──────┘
                │
         ┌──────┴──────┐
         │    s1       │ (OVS)
         └─┬────┬────┬─┘
           │    │    │
     ┌─────┘    │    └─────┐
     ▼          ▼          ▼
 h_buku    h_absen     h_admin   (wired hosts)
  
           (WiFi)
          ▲
          │
        ┌─┴───┐
        │ ap1 │───(sta1…staN)
        └─────┘
```

Komponen:

| Komponen    | Deskripsi                      |
| ----------- | ------------------------------ |
| **s1**      | Switch pusat OVS               |
| **h_buku**  | Server buku (prioritas tinggi) |
| **h_absen** | Server absensi                 |
| **h_admin** | Server admin + iperf server    |
| **ap1**     | Access point perpustakaan      |
| **STA**     | 5, 10, dan 15 pengunjung       |

Alasan *hybrid*:

* Perpustakaan memiliki **layanan inti via kabel** (lebih stabil)
* Pengunjung menggunakan **WiFi**, yang lebih rentan terhadap interferensi & kontensi

---

## 📌 **4. Penjelasan 5 Skenario Uji**

### **Skenario 1 – 5 STA, kondisi idle (tanpa trafik)**

Mengukur:

* Latency kabel (h_buku ↔ h_admin)
* Latency WiFi (sta1 → h_admin)
* Packet Loss (should 0%)

### **Skenario 2 – 10 STA, trafik visitor UDP**

* STA1–STA5 mengirim **UDP 10 Mbps** ke `h_admin`
* Mengukur throughput & packet loss per STA

### **Skenario 3 – 15 STA, QoS Prioritas**

* 5 STA mengirim background UDP 5 Mbps
* `h_buku` kirim TCP → h_admin
* Diuji apakah trafik prioritas menang bandwidth

### **Skenario 4 – 15 STA, perbandingan Idle vs Busy**

* Ping idle (tanpa trafik)
* Ping busy (dengan background UDP)
* Mengukur perubahan latency/kestabilan

### **Skenario 5 – Perbandingan 5/10/15 STA (Bandwidth vs Jumlah Pengguna)**

Semua STA mengirim UDP 5 Mbps.
Tujuan:

* Mengukur kapasitas AP/switch ketika beban meningkat
* Melihat kenaikan loss dan jitter secara jelas

---

# 📌 **5. Ringkasan Hasil Percobaan (Eksperimen 1 vs Eksperimen 2)**

## **Hasil Inti yang Konsisten:**

1. **Latency host kabel** selalu paling kecil (<1 ms setelah flow terpasang).
2. **WiFi latency** jauh lebih besar (5–20 ms), dipengaruhi banyak STA.
3. **Trafik prioritas (h_buku)** selalu menang bandwidth dibanding STA.
4. Makin banyak STA → **packet loss meningkat**, throughput efektif menurun.
5. *Idle ping* sering lebih tinggi dari *busy ping* → efek ARP/flow warm-up.

---

## 🔎 **Perbandingan Tiap Skenario**

### **✔ Skenario 1 — 5 STA (idle)**

* Latency h_buku ↔ h_admin: **0.08–0.1 ms**
* Latency sta1 → h_admin: **8–12 ms**
* **0% packet loss**
  ➡ **Konsisten** pada percobaan 1 & 2.

---

### **✔ Skenario 2 — 10 STA (trafik UDP)**

Throughput server:

| STA  | Rata-rata | Loss |
| ---- | --------- | ---- |
| sta1 | 9.0 Mbps  | 18%  |
| sta2 | 9.3 Mbps  | 7%   |
| sta3 | 9.4 Mbps  | 5%   |
| sta4 | 9.7 Mbps  | 2%   |
| sta5 | 10 Mbps   | 0%   |

➡ **Pola sama** dengan percobaan 1.
➡ Semakin banyak interferensi, loss makin tinggi.

---

### **✔ Skenario 3 — TCP prioritas vs UDP background**

Throughput TCP (prioritas):

* Run1: **94 Mbps**
* Run2: **57 Mbps**
* Run3: **48 Mbps**

➡ Sama seperti percobaan 1:

* Prioritas **berfungsi**, TCP tetap menang (bahkan sampai 94 Mbps).
* Nilai berubah karena WiFi bersifat nondeterministic.

---

### **✔ Skenario 4 — Latency Idle vs Busy**

**Percobaan 1 & 2: hasilnya SAMA:**

* *Idle ping* pertama tinggi (**20–30 ms**)
* *Busy ping* lebih stabil (**0.3–1 ms**)
  ➡ Karena:

  * ARP resolve
  * Flow table sudah terpasang
  * Cache routing aktif

Ini **fenomena simulasi SDN**, bukan WiFi fisik.

---

### **✔ Skenario 5 — Perbandingan 5, 10, 15 STA**

Hasil percobaan kedua (lebih lengkap dari percobaan 1):

| Jumlah STA | Target per STA | Total Target | Total Server             | Loss                     |
| ---------: | -------------- | ------------ | ------------------------ | ------------------------ |
|          5 | 5 Mbps         | 25 Mbps      | ~25 Mbps                 | 9–11%                    |
|         10 | 5 Mbps         | 50 Mbps      | ~48–50 Mbps              | 15–33%                   |
|         15 | 5 Mbps         | 75 Mbps      | (server mulai gagal ack) | >40% (indikasi overload) |

➡ Grafiknya sangat jelas:
“Makin banyak STA → throughput per STA tidak turun, tetapi **loss naik cepat** karena channel contention”.

---

# 📌 **6. Kenapa Menggunakan Subnet (10.0.0.x) Padahal Awalnya VLAN?**

Mininet-WiFi memiliki **keterbatasan handling VLAN di AP**, antara lain:

* Beberapa AP tidak meneruskan frame 802.1Q secara penuh.
* STA tidak stabil membaca tag VLAN.
* ARP sering gagal (kejadian yang kamu alami 2 hari).
* Ryu perlu *match* berdasarkan VLAN ID, tetapi Mininet-WiFi → AP → STA tidak selalu mengirim tag VLAN dengan benar.

Agar:

* ARP stabil
* ping antar subnet berhasil
* paket mengalir ke OVS tanpa OVS memodifikasi VLAN header
* model simulasi tidak crash

➡ **Subnetting adalah solusi paling stabil.**

### Hasilnya?

* Masih bisa memisahkan traffic (wired vs wireless).
* Bisa tetap menerapkan QoS (queue, priority).
* Tidak mengganggu arsitektur SDN.

---

# 📌 **7. Saran Peningkatan Proyek (Level Lanjut)**

### **1. Gunakan Router SDN (OVS atau Ryu Routing App)**

Jika ingin benar-benar VLAN:

* Tambah router OVS (L3)
* Buat interface VLAN seperti:

  ```
  s1.vlan10
  s1.vlan20
  ```
* Gunakan Ryu simple_router atau simple_switch_13 + VLAN rules
* STA tetap di VLAN 30 (SSID berbeda)

### **2. Gunakan Wmediumd “advanced”**

* Model interferensi lebih realistis
* Loss & jitter akan lebih konsisten dengan kondisi WiFi asli

### **3. Gunakan Traffic Shaper Tambahan**

* HTB
* Hierarchical queue
* QoS lebih detail (rate-limit tiap STA)

### **4. Buat Graph Otomatis**

Tambahkan script auto-plot (matplotlib) untuk:

* latency
* jitter
* loss
* throughput

Akan sangat bagus untuk laporan penelitian.

---

# 📌 **8. Cara Menjalankan Project**

### **Menjalankan Controller Ryu**

```bash
source ryu/bin/activate
ryu-manager vlan_sw.py
```

### **Menjalankan Topologi + Skenario**

```bash
sudo python3 perpus_final.py --mode auto
```

Output akan tersimpan di folder:

```
hasil_qos/
 ├─ skenario1.txt
 ├─ skenario2.txt
 ├─ skenario3.txt
 ├─ skenario4.txt
 └─ skenario5_bandwidth_vs_sta.txt
```

### **Mode CLI (debug manual)**

```bash
sudo python3 perpus_final.py --mode cli
```

---

# 📌 **9. Penutup**

Project ini berhasil:

* Mensimulasikan jaringan perpustakaan UPI Purwakarta secara realistis
* Menghasilkan 5 skenario QoS dengan hasil konsisten
* Menguji prioritas trafik SDN
* Membandingkan efek jumlah STA terhadap kualitas jaringan
* Menggunakan Mininet-WiFi terbaru dan Ryu sebagai SDN Controller

Dokumentasi ini membantu memahami desain, alasan teknis, dan hasil analisis secara lengkap.
