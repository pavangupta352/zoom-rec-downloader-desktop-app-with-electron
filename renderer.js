const { ipcRenderer } = require("electron");
const fs = require("fs");
const path = require("path");

document.getElementById("login-form").addEventListener("submit", (event) => {
  event.preventDefault();

  const accountId = document.getElementById("account-id").value;
  const clientId = document.getElementById("client-id").value;
  const clientSecret = document.getElementById("client-secret").value;

  const config = {
    OAuth: {
      account_id: accountId,
      client_id: clientId,
      client_secret: clientSecret,
    },
  };

  const configPath = path.join(__dirname, "zoom-recording-downloader.conf");
  fs.writeFile(configPath, JSON.stringify(config, null, 4), (err) => {
    if (err) {
      console.error("Failed to write config file", err);
      return;
    }
    ipcRenderer.send("start-python-script");
  });
});

ipcRenderer.on("python-output", (event, message) => {
  const outputElement = document.getElementById("python-output");
  if (!message.startsWith("progress:")) {
    outputElement.innerHTML += message + "<br>";
  }
});

ipcRenderer.on("python-error", (event, message) => {
  const outputElement = document.getElementById("python-output");
  outputElement.innerHTML +=
    '<span style="color: red;">' + message + "</span><br>";
});

ipcRenderer.on("python-progress", (event, progressDetails) => {
  const [percent, speed] = progressDetails.split(",");
  const progressBar = document.getElementById("progress-bar");
  if (progressBar) {
    progressBar.style.width = percent;
    progressBar.textContent = `${percent} (${speed})`;
  }
});
