// Configuration untuk optimasi
const CONFIG = {
    FRAME_INTERVAL: 2000,  // Kirim frame setiap 2 detik
    FETCH_INTERVAL: 1500,  // Fetch results setiap 1.5 detik
    CANVAS_QUALITY: 0.7,   // Kualitas JPEG untuk mengurangi size
    VIDEO_WIDTH: 640,      // Batasi resolusi video
    VIDEO_HEIGHT: 480
};

let isProcessing = false;
let lastFrameTime = 0;

// Fungsi untuk menggambar bounding boxes (optimized)
function drawBoundingBoxes(faces) {
    let video = document.getElementById("userCam");
    let overlay = document.getElementById("overlay");
    
    if (!video || !overlay) return;
    
    let ctx = overlay.getContext("2d");
    
    // Set ukuran canvas sama dengan video display size (bukan video resolution)
    const rect = video.getBoundingClientRect();
    overlay.width = rect.width;
    overlay.height = rect.height;
    overlay.style.width = rect.width + 'px';
    overlay.style.height = rect.height + 'px';
    
    // Clear canvas
    ctx.clearRect(0, 0, overlay.width, overlay.height);
    
    if (faces.length === 0) return;
    
    // Calculate scale factors
    const scaleX = overlay.width / video.videoWidth;
    const scaleY = overlay.height / video.videoHeight;
    
    // Set style untuk bounding box
    ctx.lineWidth = 2;
    ctx.font = "14px Arial";
    ctx.textBaseline = "top";
    
    faces.forEach(face => {
        if (face.face_box) {
            let { x, y, width, height } = face.face_box;
            
            // Scale coordinates
            x *= scaleX;
            y *= scaleY;
            width *= scaleX;
            height *= scaleY;
            
            // Tentukan warna berdasarkan status
            if (face.is_known) {
                ctx.strokeStyle = "#00FF00";
                ctx.fillStyle = "rgba(0, 255, 0, 0.2)";
            } else {
                ctx.strokeStyle = "#FF0000";
                ctx.fillStyle = "rgba(255, 0, 0, 0.2)";
            }
            
            // Gambar bounding box
            ctx.strokeRect(x, y, width, height);
            
            // Gambar background untuk label
            let label = face.username || "Unknown";
            let textWidth = ctx.measureText(label).width;
            
            ctx.fillRect(x, y - 20, textWidth + 8, 20);
            
            // Gambar text label
            ctx.fillStyle = "#FFFFFF";
            ctx.fillText(label, x + 4, y - 16);
        }
    });
}

// Optimized fetch recognition data
async function fetchRecognitionData() {
    try {
        let res = await fetch("/recognition_data");
        if (!res.ok) throw new Error('Network response was not ok');
        
        let data = await res.json();
        updateResultDisplay(data);
        drawBoundingBoxes(data);
    } catch (err) {
        console.error('Fetch error:', err);
        // Show error in result box
        let resultBox = document.getElementById("result");
        if (resultBox) {
            resultBox.innerHTML = "<li style='color: orange;'>Connection error. Retrying...</li>";
        }
    }
}

function updateResultDisplay(data) {
    let resultBox = document.getElementById("result");
    if (!resultBox) return;
    
    resultBox.innerHTML = ""; 

    if (data.length === 0) {
        resultBox.innerHTML = "<li>No face detected</li>";
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
    }
}

// Initialize camera with constraints
async function initializeCamera() {
    try {
        const constraints = {
            video: {
                width: { ideal: CONFIG.VIDEO_WIDTH },
                height: { ideal: CONFIG.VIDEO_HEIGHT },
                frameRate: { ideal: 15, max: 20 }  // Limit framerate
            }
        };
        
        const stream = await navigator.mediaDevices.getUserMedia(constraints);
        let video = document.getElementById("userCam");
        if (video) {
            video.srcObject = stream;
            
            // Set ukuran overlay canvas ketika video ready
            video.addEventListener('loadedmetadata', () => {
                let overlay = document.getElementById("overlay");
                if (overlay) {
                    const rect = video.getBoundingClientRect();
                    overlay.width = rect.width;
                    overlay.height = rect.height;
                    overlay.style.width = rect.width + 'px';
                    overlay.style.height = rect.height + 'px';
                }
            });
            
            // Handle video resize
            video.addEventListener('resize', () => {
                setTimeout(() => {
                    let overlay = document.getElementById("overlay");
                    if (overlay) {
                        const rect = video.getBoundingClientRect();
                        overlay.width = rect.width;
                        overlay.height = rect.height;
                        overlay.style.width = rect.width + 'px';
                        overlay.style.height = rect.height + 'px';
                    }
                }, 100);
            });
        }
    } catch (err) {
        console.error("Camera error:", err);
        let resultBox = document.getElementById("result");
        if (resultBox) {
            resultBox.innerHTML = "<li style='color: red;'>Camera access denied or unavailable</li>";
        }
    }
}

// Optimized frame sending with throttling
async function sendFrameToServer() {
    const currentTime = Date.now();
    
    // Throttle frame sending
    if (isProcessing || currentTime - lastFrameTime < CONFIG.FRAME_INTERVAL) {
        return;
    }
    
    isProcessing = true;
    lastFrameTime = currentTime;
    
    try {
        let video = document.getElementById("userCam");
        if (!video || video.readyState !== video.HAVE_ENOUGH_DATA) {
            return;
        }
        
        let canvas = document.getElementById("snapshot");
        if (!canvas) return;
        
        let ctx = canvas.getContext("2d");
        
        // Use smaller canvas size for processing
        const processWidth = Math.min(video.videoWidth, CONFIG.VIDEO_WIDTH);
        const processHeight = Math.min(video.videoHeight, CONFIG.VIDEO_HEIGHT);
        
        canvas.width = processWidth;
        canvas.height = processHeight;
        
        ctx.drawImage(video, 0, 0, processWidth, processHeight);
        
        // Lower quality for faster upload
        let frameData = canvas.toDataURL("image/jpeg", CONFIG.CANVAS_QUALITY);

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 5000); // 5 second timeout
        
        let res = await fetch("/process_frame", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ frame: frameData }),
            signal: controller.signal
        });
        
        clearTimeout(timeoutId);
        
        if (res.ok) {
            let data = await res.json();
            updateResultDisplay(data);
            drawBoundingBoxes(data);
        } else {
            throw new Error('Server response not ok');
        }
        
    } catch (err) {
        if (err.name === 'AbortError') {
            console.log('Request timed out');
        } else {
            console.error('Frame processing error:', err);
        }
        
        let resultBox = document.getElementById("result");
        if (resultBox) {
            resultBox.innerHTML = "<li style='color: orange;'>Processing timeout. Retrying...</li>";
        }
    } finally {
        isProcessing = false;
    }
}

// Initialize everything when page loads
document.addEventListener('DOMContentLoaded', () => {
    initializeCamera();
    
    // Start intervals with different timings to avoid conflicts
    setInterval(sendFrameToServer, CONFIG.FRAME_INTERVAL);
    setTimeout(() => {
        setInterval(fetchRecognitionData, CONFIG.FETCH_INTERVAL);
    }, 500); // Start fetch slightly after first frame send
});

// ==============================
// Database Users Table + Search (tidak berubah)
// ==============================
let allUsers = [];

function highlightText(text, keyword) {
    if (!keyword) return text;
    let regex = new RegExp(`(${keyword})`, "gi");
    return text.replace(regex, "<mark>$1</mark>");
}

async function loadUsers() {
    try {
        let response = await fetch("/users");
        allUsers = await response.json(); 
        renderUsers(allUsers);
    } catch (err) {
        console.error('Error loading users:', err);
    }
}

function renderUsers(users, keyword = "") {
    let tbody = document.getElementById("user-body");
    if (!tbody) return;
    
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

// Search functionality
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
            renderUsers(filtered, this.value);
        });
    }
});

async function deleteUser(user_id) {
    if (confirm("Yakin hapus user ini?")) {
        try {
            await fetch(`/delete_user/${user_id}`, { method: "POST" });
            loadUsers();
        } catch (err) {
            console.error('Error deleting user:', err);
            alert('Error deleting user');
        }
    }
}

// Load users on page load
loadUsers();