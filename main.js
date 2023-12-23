const { app, BrowserWindow, ipcMain } = require("electron");
const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");

let pyProc = null;
let mainWindow = null;

function createPyProc() {
  const scriptPath = path.join(__dirname, "zoom-recording-downloader.py");
  pyProc = spawn("python", [scriptPath]);

  if (pyProc != null) {
    console.log("Child process successful");

    pyProc.stdout.on("data", (data) => {
      const message = data.toString();
      if (message.startsWith("electron_progress:")) {
        // Extract and send progress details to renderer process
        const progressDetails = message.split("electron_progress:")[1].trim();
        mainWindow.webContents.send("python-progress", progressDetails);
      } else {
        // Log other messages in the terminal/console
        console.log(`stdout: ${message}`);
      }
    });

    pyProc.stderr.on("data", (data) => {
      console.error(`stderr: ${data}`);
      mainWindow.webContents.send("python-error", data.toString());
    });

    pyProc.on("close", (code) => {
      console.log(`Child process exited with code ${code}`);
      pyProc = null;
    });

    setTimeout(() => {
      pyProc.stdin.write("start\n");
    }, 1000);
  }
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 800,
    height: 600,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
    },
  });

  mainWindow.loadFile("index.html");
  mainWindow.webContents.openDevTools();
}

app.whenReady().then(createWindow);

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

ipcMain.on("start-python-script", () => {
  if (!pyProc) {
    createPyProc();
  } else {
    console.log("Python script is already running.");
  }
});

function clearAccessToken() {
  const tokenPath = path.join(__dirname, "access_token.json");
  if (fs.existsSync(tokenPath)) {
    fs.unlinkSync(tokenPath);
    console.log("Access token cleared.");
  }
}

app.on("before-quit", () => {
  clearAccessToken();
  if (pyProc) {
    pyProc.kill();
  }
});

ipcMain.on("login-credentials", (event, args) => {
  console.log("Received login credentials in main process:", args);
});
