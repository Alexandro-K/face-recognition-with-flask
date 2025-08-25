// Fungsi untuk menggambar bounding box
function drawBoundingBoxes(faces) {
    let video = document.getElementById("userCam");
    let overlay = document.getElementById("overlay");
    let ctx = overlay.getContext("2d");
    
    // Set ukuran canvas sama dengan video
    overlay.width = video.videoWidth;
    overlay.height = video.videoHeight;
    
    // Clear canvas
    ctx.clearRect(0, 0, overlay.width, overlay.height);
    
    // Set style untuk bounding box
    ctx.lineWidth = 3;
    ctx.font = "16px Arial";
    ctx.textBaseline = "top";
    
    faces.forEach(face => {
        if (face.face_box) {
            let { x, y, width, height } = face.face_box;
            
            // Tentukan warna berdasarkan status
            if (face.is_known) {
                ctx.strokeStyle = "#00FF00"; // Hijau untuk wajah dikenal
                ctx.fillStyle = "rgba(0, 255, 0, 0.3)";
            } else {
                ctx.strokeStyle = "#FF0000"; // Merah untuk wajah tidak dikenal
                ctx.fillStyle = "rgba(255, 0, 0, 0.3)";
            }
            
            // Gambar bounding box
            ctx.strokeRect(x, y, width, height);
            
            // Gambar background untuk label
            let label = face.username || "Unknown";
            let textWidth = ctx.measureText(label).width;
            
            ctx.fillRect(x, y - 25, textWidth + 10, 25);
            
            // Gambar text label
            ctx.fillStyle = "#FFFFFF";
            ctx.fillText(label, x + 5, y - 20);
        }
    });
}

async function fetchRecognitionData() {
    try {
        let res = await fetch("/recognition_data");
        let data = await res.json();
        let resultBox = document.getElementById("result");
        resultBox.innerHTML = ""; 

        if (data.length === 0) {
            resultBox.innerHTML = "<li>No face detected</li>";
            // Clear bounding boxes jika tidak ada wajah
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
            // Gambar bounding boxes
            drawBoundingBoxes(data);
        }
    } catch (err) {
        console.error(err);
    }
}

// Aktifkan kamera user
navigator.mediaDevices.getUserMedia({ video: true })
  .then(stream => {
    let video = document.getElementById("userCam");
    video.srcObject = stream;
    
    // Set ukuran overlay canvas ketika video ready
    video.addEventListener('loadedmetadata', () => {
        let overlay = document.getElementById("overlay");
        overlay.width = video.videoWidth;
        overlay.height = video.videoHeight;
    });
  })
  .catch(err => console.error("Camera error:", err));

async function sendFrameToServer() {
    let video = document.getElementById("userCam");
    let canvas = document.getElementById("snapshot");
    let ctx = canvas.getContext("2d");

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    ctx.drawImage(video, 0, 0);

    let frameData = canvas.toDataURL("image/jpeg");

    try {
        let res = await fetch("/process_frame", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ frame: frameData })
        });
        let data = await res.json();

        // Tampilkan hasil
        let resultBox = document.getElementById("result");
        resultBox.innerHTML = "";
        if (data.length === 0) {
            resultBox.innerHTML = "<li>No face detected</li>";
            // Clear bounding boxes
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
            // Gambar bounding boxes
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

// ==============================
// Database Users Table + Search
// ==============================
let allUsers = []; // simpan semua user untuk filter client-side


function highlightText(text, keyword) {
    if (!keyword) return text;
    let regex = new RegExp(`(${keyword})`, "gi"); // case insensitive
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
    if (confirm("Yakin hapus user ini?")) {
        await fetch(`/delete_user/${user_id}`, { method: "POST" });
        loadUsers(); // refresh tabel setelah delete
    }
}

// Load users pertama kali
loadUsers();