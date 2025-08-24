// ==============================
// Face Recognition Result
// ==============================
async function fetchRecognitionData() {
    try {
        let res = await fetch("/recognition_data");
        let data = await res.json();
        let resultBox = document.getElementById("result");
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
    } catch (err) {
        console.error(err);
    }
}

// Refresh tiap 5 detik
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
