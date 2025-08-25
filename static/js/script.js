// Fungsi untuk menggambar bounding box
function drawBoundingBoxes(faces) {
    let video = document.getElementById("userCam"); // Mengambil webcam pengguna
    let overlay = document.getElementById("overlay");  // Mengambil overlay yang akan digunakan untuk menggambar bbox
    let ctx = overlay.getContext("2d"); // Context 2d untuk memungkinkan kita membuat gambar teks, bentuk, dan warna
    
    // Set ukuran canvas sama dengan video
    overlay.width = video.videoWidth; // Megatur lebar agar sama dengan video
    overlay.height = video.videoHeight; // Megatur tinggi agar sama dengan video
    
    // Clear canvas
    ctx.clearRect(0, 0, overlay.width, overlay.height);
    
    // Set style untuk bounding box
    ctx.lineWidth = 3;
    ctx.font = "16px Arial";
    ctx.textBaseline = "top";
    
    // Looping untuk setiap wajah
    faces.forEach(face => {
        if (face.face_box) { // Jika wajah terdeksi ambil face_boxnya (x, y, w, h)
            let { x, y, width, height } = face.face_box;
            
            // Tentukan warna berdasarkan status
            if (face.is_known) {
                // Jika wajah dikenal
                ctx.strokeStyle = "#00FF00"; 
                ctx.fillStyle = "rgba(0, 255, 0, 0.3)";
            } else {
                // Jika wajah tidak dikenal
                ctx.strokeStyle = "#FF0000"; 
                ctx.fillStyle = "rgba(255, 0, 0, 0.3)";
            }
            
            // Gambar bounding box
            ctx.strokeRect(x, y, width, height);
            
            // Gambar background untuk label
            let label = face.username || "Unknown";
            let textWidth = ctx.measureText(label).width;
            
            // (x, y - 25(diatas sedikit), lebar text + 10 (agar tidak menempel), tinggi kotak)
            ctx.fillRect(x, y - 25, textWidth + 10, 25);
            
            // Gambar text label
            ctx.fillStyle = "#FFFFFF";
            ctx.fillText(label, x + 5, y - 20); // (Teks, posisi kiri atas)
        }
    });
}

// Asinkronus function untuk mengambil data ( mengambil data terakhir yang sudah dikenali oleh server)
async function fetchRecognitionData() {
    try {
        let res = await fetch("/recognition_data"); // Request data ke recognition_data
        let data = await res.json(); // Konversi hasil ke array json
        let resultBox = document.getElementById("result"); // Mengambil result di html
        resultBox.innerHTML = ""; // Mengosongkan hasilnya

        // Jika kosong ( tidak ada yang terdeteksi )
        if (data.length === 0) {
            resultBox.innerHTML = "<li>No face detected</li>";
            drawBoundingBoxes([]);
        }
        // Jika ada yang terdeteksi 
        else {
            data.forEach(user => {
                let li = document.createElement("li"); // Membuat li
                // Untuk setiap user yang dideteksi ( tampilkan datanya )
                li.innerHTML = `
                    <div><strong>ID:</strong> ${user.user_id ?? '-'}</div>
                    <div><strong>Nama:</strong> ${user.username}</div>
                    <div><strong>Jenis Kelamin:</strong> ${user.jenis_kelamin}</div>
                    <div><strong>Jurusan:</strong> ${user.jurusan}</div>
                `;
                resultBox.appendChild(li);
            });
            // Gambar bounding boxnya berdasarkan user yang terdeteksi
            drawBoundingBoxes(data);
        }
    } catch (err) {
        console.error(err);
    }
}

// Aktifkan kamera user
navigator.mediaDevices.getUserMedia({ video: true }) // API untuk mengambil stream dari kamera user
  .then(stream => {
    let video = document.getElementById("userCam"); // Mengambil userCam untuk mengampilkan video
    video.srcObject = stream; // Menampilkan videonya
    
    // Set ukuran overlay canvas ketika video ready ( kondiisi dimana video sudah benar-benar ready )
    video.addEventListener('loadedmetadata', () => {
        let overlay = document.getElementById("overlay");
        overlay.width = video.videoWidth;
        overlay.height = video.videoHeight;
    });
  })
  .catch(err => console.error("Camera error:", err));

// ( Mengambil data untuk membandingkan data baru yang belum dikenali )
async function sendFrameToServer() {
    // Mengambil elemen dari html dan membuat context
    let video = document.getElementById("userCam");
    let canvas = document.getElementById("snapshot");
    let ctx = canvas.getContext("2d");

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    ctx.drawImage(video, 0, 0); // Menyalin frame video ke kanvas

    let frameData = canvas.toDataURL("image/jpeg"); // Mengubah kanvas menjadi string base64

    try {
        let res = await fetch("/process_frame", { // Mengambil process_frame untuk mendapatkan user yang terdeksi
            method: "POST", // Melakukan post frame
            headers: { "Content-Type": "application/json" }, // Memberikan konten dalam bentuk json
            body: JSON.stringify({ frame: frameData }) // Mengubah menjadi string json
        });
        let data = await res.json(); 

        // Tampilkan hasil
        let resultBox = document.getElementById("result");
        resultBox.innerHTML = "";
        if (data.length === 0) {
            resultBox.innerHTML = "<li>No face detected</li>";
            drawBoundingBoxes([]);
        } else {
            data.forEach(user => {
                let li = document.createElement("li");
                li.innerHTML = `
                    <div><strong>ID:</strong> ${user.user_id ?? '-'}</div>
                    <div><strong>Nama:</strong> ${user.username}</div>
                    <div><strong>Jenis Kelamin:</strong> ${user.jenis_kelamin}</div>
                    <div><strong>Jurusan:</strong> ${user.jurusan}</div>
                `;
                resultBox.appendChild(li);
            });
            drawBoundingBoxes(data);
        }
    } catch (err) {
        console.error(err);
    }
}

// Kirim frame tiap 1 detik
setInterval(sendFrameToServer, 1000);

// Refresh tiap 1 detik
setInterval(fetchRecognitionData, 1000);

let allUsers = []; // simpan semua user untuk filter client-side

function highlightText(text, keyword) {
    if (!keyword) return text; //Jika tidak ada keyword yang dicari return text utuh
    let regex = new RegExp(`(${keyword})`, "gi"); // Global & case insensitive 
    return text.replace(regex, "<mark>$1</mark>");
}

// Ambil semua user dari API
async function loadUsers() {
    let response = await fetch("/users");
    allUsers = await response.json(); 
    renderUsers(allUsers);
}

// Render tabel user
function renderUsers(users, keyword = "") {
    let tbody = document.getElementById("user-body");
    tbody.innerHTML = ""; 

    users.forEach(user => {
        //  Membuat table row yang masing-masing berisikan data pengguna
        let tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${highlightText(user.user_id + "", keyword)}</td>
            <td>${highlightText(user.username ?? "", keyword)}</td>
            <td>${highlightText(user.jenis_kelamin ?? "", keyword)}</td>
            <td>${highlightText(user.jurusan ?? "", keyword)}</td>
            <td>
                <button class="delete-btn" onclick="deleteUser('${user.user_id}')">Delete</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}


// Fungsi search/filter tabel user
document.addEventListener("DOMContentLoaded", () => {
    let searchInput = document.getElementById("search-input");
    if (searchInput) {
        searchInput.addEventListener("keyup", function() {
            let keyword = this.value.toLowerCase();
            // Memfilter apabila salah satu data dari database memenuhi keyword
            let filtered = allUsers.filter(user => 
                (user.username && user.username.toLowerCase().includes(keyword)) ||
                (user.jenis_kelamin && user.jenis_kelamin.toLowerCase().includes(keyword)) ||
                (user.jurusan && user.jurusan.toLowerCase().includes(keyword)) ||
                (user.user_id && (user.user_id + "").toLowerCase().includes(keyword))
            );
            renderUsers(filtered, this.value); // kirim keyword asli (bukan lowercase)
        });
    }
});


// Hapus user
async function deleteUser(user_id) {
    if (confirm("Hapus user ini?")) {
        await fetch(`/delete_user/${user_id}`, { method: "POST" });
        loadUsers(); // refresh tabel setelah delete
    }
}

// Load users pertama kali
loadUsers();