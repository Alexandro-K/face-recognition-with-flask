async function fetchRecognitionData() {
    try {
        let res = await fetch("/recognition_data");
        let data = await res.json();
        let resultBox = document.getElementById("result");
        resultBox.innerHTML = ""; // reset isi

        if (data.length === 0) {
            resultBox.innerHTML = "<li>No face detected</li>";
        } else {
            data.forEach(user => {
            let li = document.createElement("li");
            li.innerHTML = `
                <div><strong>ID:</strong> ${user.user_id ?? '-'}</div>
                <div><strong>Nama:</strong> ${user.username}</div>
                <div><strong>Jurusan:</strong> ${user.major}</div>
            `;
            resultBox.appendChild(li);
    });
}

    } catch (err) {
        console.error(err);
    }
}

// refresh tiap 1 detik
setInterval(fetchRecognitionData, 1000);

async function loadUsers() {
    let response = await fetch("/users");
    let users = await response.json();

    let tbody = document.getElementById("user-body");
    tbody.innerHTML = ""; // reset isi tabel

    users.forEach(user => {
        let tr = document.createElement("tr");

        tr.innerHTML = `
            <td>${user.user_id}</td>
            <td>${user.username}</td>
            <td>${user.major}</td>
            <td>
                <button class="delete-btn" onclick="deleteUser('${user.user_id}')">Delete</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

async function deleteUser(user_id) {
    if (confirm("Yakin hapus user ini?")) {
        await fetch(`/delete_user/${user_id}`, { method: "POST" });
        loadUsers(); // refresh tabel setelah delete
    }
}

// Load users saat halaman pertama kali dibuka
loadUsers();