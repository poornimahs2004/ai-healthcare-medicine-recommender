// backend/static/script.js

// --- CONFIGURATION ---
const SYMPTOMS = [
  "fever",
  "cough",
  "headache",
  "sore_throat",
  "runny_nose",
  "sneezing",
  "body_ache",
  "fatigue",
  "chills",
  "nausea",
  "vomiting",
  "diarrhea",
  "shortness_of_breath",
  "congestion",
  "watery_eyes",
  "itchy_eyes",
  "joint_pain",
  "muscle_pain",
  "abdominal_pain",
  "chest_pain",
  "dizziness",
  "migraine",
  "rash",
  "back_pain",
  "neck_pain",
  "insomnia",
  "anxiety",
  "dry_skin",
  "sweating",
  "weakness",
];

let selectedSymptoms = [];
let currentUserId = sessionStorage.getItem("token");
let userLat = null;
let userLon = null;

// --- NAVIGATION ---
function switchTab(tabId) {
  document
    .querySelectorAll(".view-tab")
    .forEach((el) => el.classList.add("hidden"));
  const target = document.getElementById("tab-" + tabId);
  if (target) target.classList.remove("hidden");

  document
    .querySelectorAll(".nav-item")
    .forEach((btn) => btn.classList.remove("nav-active"));
  const activeBtn = document.getElementById("btn-" + tabId);
  if (activeBtn) activeBtn.classList.add("nav-active");
}

function showPage(pageId) {
  ["welcome", "login", "register", "app"].forEach((id) =>
    document.getElementById(`page-${id}`).classList.add("hidden")
  );
  document.getElementById(`page-${pageId}`).classList.remove("hidden");

  if (pageId === "app") {
    lucide.createIcons();
    loadHistory();
    filterS("");
    switchTab("plan");
  }
}

function logout() {
  sessionStorage.removeItem("token");
  currentUserId = null;
  showPage("welcome");
}

// --- AUTHENTICATION ---
async function auth(type) {
  const email = document.getElementById(
    type === "login" ? "l-email" : "r-email"
  ).value;
  const pass = document.getElementById(
    type === "login" ? "l-pass" : "r-pass"
  ).value;
  const phone =
    type === "register" ? document.getElementById("r-phone").value : null;
  const msg = document.getElementById(type === "login" ? "l-msg" : "r-msg");

  if (!email || !pass) {
    msg.innerText = "Please fill in all fields.";
    msg.classList.remove("hidden");
    return;
  }

  try {
    const res = await fetch(`/auth/${type}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password: pass, phone }),
    });
    const data = await res.json();

    if (res.ok) {
      if (type === "login") {
        sessionStorage.setItem("token", data.user_id);
        currentUserId = data.user_id;
        showPage("app");
      } else {
        msg.innerText = "Success! Please Login.";
        msg.style.color = "green";
        msg.classList.remove("hidden");
        setTimeout(() => showPage("login"), 1500);
      }
    } else {
      msg.innerText = data.error;
      msg.style.color = "#ef4444";
      msg.classList.remove("hidden");
    }
  } catch (e) {
    alert("Connection Failed.");
  }
}

// --- MAPS & GPS ---

function getMyLocation() {
  if (!navigator.geolocation) return alert("Geolocation not supported.");

  const btn = document.querySelector('button[onclick="getMyLocation()"]');
  const originalText = btn.innerHTML;
  btn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i> GPS...`;
  lucide.createIcons();

  const options = { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 };

  navigator.geolocation.getCurrentPosition(
    (pos) => {
      userLat = pos.coords.latitude;
      userLon = pos.coords.longitude;

      document.getElementById("d-loc").value = `${userLat.toFixed(
        5
      )}, ${userLon.toFixed(5)}`;

      btn.innerHTML = `<i data-lucide="check" class="w-4 h-4"></i> Active`;
      btn.classList.replace("bg-red-50", "bg-green-100");
      btn.classList.replace("text-red-600", "text-green-700");
      lucide.createIcons();

      findDocs();
    },
    (err) => {
      alert("GPS Error: " + err.message);
      btn.innerHTML = originalText;
    },
    options
  );
}

async function findDocs() {
  const spec = document.getElementById("d-spec").value || "Hospital";
  let loc = document.getElementById("d-loc").value || "Nearby";

  // 1. MAP QUERY
  let mapQuery = "";
  if (
    userLat &&
    userLon &&
    (loc.includes(userLat.toFixed(5)) || loc === "Current Location")
  ) {
    mapQuery = `${spec} near ${userLat},${userLon}`;
    loc = `${userLat},${userLon}`;
  } else {
    mapQuery = `${spec} near ${loc}`;
  }

  // 2. UPDATE IFRAME (FIXED URL HERE)
  const mapFrame = document.getElementById("gmap-frame");
  const encodedQuery = encodeURIComponent(mapQuery);
  // The correct standard format:
  mapFrame.src = `https://maps.google.com/maps?q=${encodedQuery}&t=&z=14&ie=UTF8&iwloc=&output=embed`;

  // 3. FETCH LIST
  const listDiv = document.getElementById("d-list");
  listDiv.innerHTML =
    '<p class="text-slate-400 p-2 text-sm animate-pulse">Scanning area...</p>';

  const payload = { specialty: spec, location: loc };
  if (userLat && userLon && loc.includes(userLat.toFixed(5))) {
    payload.lat = userLat;
    payload.lon = userLon;
  }

  try {
    const res = await fetch("/doctors", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    listDiv.innerHTML = "";

    if (data.result && data.result.length > 0) {
      data.result.forEach((doc) => {
        listDiv.innerHTML += `
                  <div onclick="focusMap('${doc.name}', '${
          doc.address
        }')" class="bg-slate-50 p-4 rounded-xl border border-slate-100 hover:shadow-md transition hover:bg-white group cursor-pointer hover:border-blue-400">
                    <div class="flex justify-between items-start mb-2">
                        <h4 class="font-bold text-slate-800 group-hover:text-blue-600 transition">${
                          doc.name
                        }</h4>
                        <span class="bg-white text-green-700 border border-green-200 text-xs font-bold px-2 py-1 rounded-md flex items-center gap-1">⭐ ${
                          doc.rating || "N/A"
                        }</span>
                    </div>
                    <p class="text-xs text-slate-500 truncate flex items-center gap-1"><i data-lucide="map-pin" class="w-3 h-3"></i> ${
                      doc.address
                    }</p>
                    <p class="text-xs text-blue-500 mt-2 font-semibold">Click to view on map →</p>
                  </div>
                `;
      });
      lucide.createIcons();
    } else {
      listDiv.innerHTML =
        '<p class="text-slate-400 text-center text-sm col-span-2">No specific details found. Map works above.</p>';
    }
  } catch (e) {
    listDiv.innerHTML =
      '<p class="text-red-400 text-sm">Error loading details.</p>';
  }
}

function focusMap(name, address) {
  const mapFrame = document.getElementById("gmap-frame");
  // FIXED URL HERE TOO
  const query = encodeURIComponent(`${name}, ${address}`);
  mapFrame.src = `https://maps.google.com/maps?q=${query}&t=&z=17&ie=UTF8&iwloc=&output=embed`;
  mapFrame.scrollIntoView({ behavior: "smooth", block: "center" });
}

// --- OTHER LOGIC ---
function filterS(q) {
  const box = document.getElementById("s-box");
  if (!box) return;
  box.innerHTML = "";
  SYMPTOMS.filter((s) => s.includes(q.toLowerCase())).forEach((s) => {
    const d = document.createElement("div");
    d.className = `p-3 rounded-lg cursor-pointer transition border font-medium text-sm flex items-center gap-2 ${
      selectedSymptoms.includes(s)
        ? "bg-blue-500 text-white border-blue-500 shadow-md transform scale-105"
        : "bg-white text-slate-600 hover:bg-slate-50 border-slate-200"
    }`;
    d.innerHTML = selectedSymptoms.includes(s)
      ? `<i data-lucide="check" class="w-3 h-3"></i> ${s.replace(/_/g, " ")}`
      : s.replace(/_/g, " ");
    d.onclick = () => {
      if (selectedSymptoms.includes(s))
        selectedSymptoms = selectedSymptoms.filter((x) => x !== s);
      else selectedSymptoms.push(s);
      filterS(document.getElementById("cp-search").value);
    };
    box.appendChild(d);
  });
  lucide.createIcons();
}

async function getPlan() {
  const age = document.getElementById("cp-age").value || 30;
  if (!selectedSymptoms.length)
    return alert("Please select at least one symptom.");

  const btn = document.querySelector('button[onclick="getPlan()"]');
  const oldText = btn.innerText;
  btn.innerHTML = `<i data-lucide="loader" class="w-5 h-5 animate-spin"></i> Analyzing...`;
  lucide.createIcons();
  btn.disabled = true;

  try {
    const res = await fetch("/recommend", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        symptoms: selectedSymptoms,
        age,
        user_id: currentUserId,
      }),
    });
    const d = await res.json();
    document.getElementById("r-disease").innerText = d.disease;
    document.getElementById("r-desc").innerText = d.description;
    document.getElementById("r-med").innerText = d.medicine;
    document.getElementById("r-diet").innerText = d.diet;
    document.getElementById("r-work").innerText = d.workouts;
    document.getElementById("r-prec").innerText = d.precautions;
    document.getElementById("res-box").classList.remove("hidden");
    document.getElementById("res-box").scrollIntoView({ behavior: "smooth" });
    loadHistory();
  } catch (e) {
    alert("Analysis Error.");
  }
  btn.innerText = oldText;
  btn.disabled = false;
}

async function sendChat() {
  const inp = document.getElementById("c-in");
  const txt = inp.value;
  if (!txt) return;
  const box = document.getElementById("chat-box");
  box.innerHTML += `<div class="flex justify-end fade-in"><div class="chat-bubble user-bubble shadow">${txt}</div></div>`;
  inp.value = "";
  box.scrollTop = box.scrollHeight;

  const res = await fetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query: txt }),
  });
  const d = await res.json();
  box.innerHTML += `<div class="flex justify-start fade-in"><div class="chat-bubble ai-bubble shadow">${d.response}</div></div>`;
  box.scrollTop = box.scrollHeight;
}

async function loadHistory() {
  const list = document.getElementById("hist-list");
  try {
    const res = await fetch(`/history?user_id=${currentUserId}`);
    const d = await res.json();
    list.innerHTML = "";
    if (data.length === 0) {
      list.innerHTML =
        '<p class="text-slate-400 text-sm italic text-center py-10">No history records found.</p>';
      return;
    }
    data.forEach((i) => {
      list.innerHTML += `
                <div class="bg-white p-4 rounded-xl border border-slate-100 shadow-sm hover:shadow-md transition mb-3">
                    <div class="flex justify-between items-center mb-2">
                        <h4 class="font-bold text-blue-900">${i.disease}</h4>
                        <span class="text-xs text-slate-500 bg-slate-100 px-2 py-1 rounded">${i.date}</span>
                    </div>
                    <p class="text-sm text-slate-600 line-clamp-2">${i.description}</p>
                </div>`;
    });
  } catch (e) {}
}

// --- INIT ---
document.addEventListener("DOMContentLoaded", () => {
  lucide.createIcons();
  if (currentUserId) showPage("app");
});

// --- FEATURE 4: PDF DOWNLOAD ---
async function downloadReport() {
  const btn = document.querySelector('button[onclick="downloadReport()"]');
  const originalText = btn.innerHTML;
  btn.innerHTML = `<i data-lucide="loader" class="w-4 h-4 animate-spin"></i> Generating...`;
  btn.disabled = true;

  // Gather data from the UI
  const payload = {
    disease: document.getElementById("r-disease").innerText,
    description: document.getElementById("r-desc").innerText,
    medicine: document.getElementById("r-med").innerText,
    diet: document.getElementById("r-diet").innerText,
    workouts: document.getElementById("r-work").innerText,
    precautions: document.getElementById("r-prec").innerText,
  };

  try {
    const res = await fetch("/download_report", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (res.ok) {
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);

      // OPEN IN NEW TAB
      window.open(url, "_blank");

      // Clean up
      setTimeout(() => window.URL.revokeObjectURL(url), 100);
    } else {
      alert("Failed to generate PDF.");
    }
  } catch (e) {
    alert("Error downloading report.");
  }

  btn.innerHTML = originalText;
  btn.disabled = false;
  lucide.createIcons(); // Re-render icon
}

// --- FEATURE 4: PDF DOWNLOAD ---
async function downloadReport() {
  // 1. Check if data exists
  const disease = document.getElementById("r-disease").innerText;
  if (!disease) return alert("Please generate a Care Plan first!");

  const btn = document.querySelector('button[onclick="downloadReport()"]');
  const oldText = btn.innerHTML;
  btn.innerHTML = `<i data-lucide="loader" class="w-4 h-4 animate-spin"></i> Generating...`;
  btn.disabled = true;

  // 2. Gather Data
  const payload = {
    disease: disease,
    description: document.getElementById("r-desc").innerText,
    medicine: document.getElementById("r-med").innerText,
    diet: document.getElementById("r-diet").innerText,
    workouts: document.getElementById("r-work").innerText,
    precautions: document.getElementById("r-prec").innerText,
  };

  try {
    // 3. Send to Backend
    const res = await fetch("/download_report", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (res.ok) {
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `CareAI_Report_${new Date().toISOString().slice(0, 10)}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } else {
      alert("Failed to generate PDF. Check server logs.");
    }
  } catch (e) {
    alert("Network Error.");
  }

  btn.innerHTML = oldText;
  btn.disabled = false;
  lucide.createIcons();
}
