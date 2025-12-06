console.log(" Script loaded!"); // To confirm JS is working

async function fetchStatus() {
  try {
    const res = await fetch("/status");
    const data = await res.json();

    // Update student info
    document.getElementById("studentName").innerText = data.name || "Detecting...";
    document.getElementById("studentId").innerText = data.id ? `ID: ${data.id}` : "ID: -";
    document.getElementById("studentMajor").innerText = data.major ? `Major: ${data.major}` : "Major: -";

    // Update photo
    const photoElem = document.getElementById("studentPhoto");
    if (data.photo_data) {
      photoElem.src = data.photo_data;
    } else {
      photoElem.src = "";
    }

    //  Update status text on webpage
    const statusElem = document.getElementById("statusText");
    const statusMsg = data.status || "Idle";
    statusElem.innerText = statusMsg;

    //  Add colors for clarity
    if (statusMsg.includes("No active lecture")) {
      statusElem.style.color = "orange";
    } else if (statusMsg.includes("marked")) {
      statusElem.style.color = "green";
    } else {
      statusElem.style.color = "gray";
    }

  } catch (err) {
    console.error("Error fetching status:", err);
  }
}

// Fetch status every 2 seconds
setInterval(fetchStatus, 2000);

//  Enable Location
document.getElementById("allowLocationBtn").addEventListener("click", () => {
  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition((pos) => {
      fetch("/update_location", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          lat: pos.coords.latitude,
          lon: pos.coords.longitude
        })
      })
        .then((res) => res.json())
        .then((data) => {
          if (data.ok) {
            alert(" Location sent successfully!");
          } else {
            alert(" Failed to send location.");
          }
        });
    });
  } else {
    alert(" Geolocation not supported.");
  }
});
