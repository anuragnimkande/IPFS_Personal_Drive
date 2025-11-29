// Utility functions
function escapeHtml(s) {
  return String(s).replace(
    /[&<>"']/g,
    (m) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      }[m])
  );
}

async function apiJson(url, opts = {}) {
  opts.credentials = opts.credentials || "same-origin";
  const r = await fetch(url, opts);
  let j = null;
  try {
    j = await r.json();
  } catch (e) {
    /* non-json response */
  }
  return { ok: r.ok, status: r.status, json: j, resp: r };
}

// File upload functionality
function initializeUpload() {
  const overlay = document.getElementById("loadingOverlay");
  const loadingText = document.getElementById("loadingText");
  const uploadArea = document.getElementById("uploadArea");
  const fileInput = document.getElementById("fileInput");
  const uploadButton = document.getElementById("uploadButton");
  const filePreview = document.getElementById("filePreview");
  const previewContent = document.getElementById("previewContent");

  // Upload area click handler
  if (uploadArea) {
    uploadArea.addEventListener("click", () => fileInput.click());
  }

  // File input change handler
  if (fileInput) {
    fileInput.addEventListener("change", function () {
      const file = fileInput.files[0];
      if (!file) return;

      if (uploadButton) uploadButton.disabled = false;
      if (filePreview) filePreview.style.display = "block";
      if (previewContent) previewContent.innerHTML = "";

      const reader = new FileReader();
      const name = file.name.toLowerCase();

      if (name.match(/\.(jpg|jpeg|png|gif|bmp|webp)$/)) {
        reader.onload = (e) =>
          (previewContent.innerHTML = `<img src="${e.target.result}" style="max-width:100%; border-radius:8px;">`);
        reader.readAsDataURL(file);
      } else if (name.endsWith(".pdf")) {
        reader.onload = (e) =>
          (previewContent.innerHTML = `<iframe src="${e.target.result}" style="width:100%;height:250px;border:none;"></iframe>`);
        reader.readAsDataURL(file);
      } else if (name.match(/\.(txt|csv|json|log|py|html|js|css)$/)) {
        reader.onload = (e) =>
          (previewContent.innerHTML = `<pre style="white-space:pre-wrap; margin:0;">${e.target.result}</pre>`);
        reader.readAsText(file);
      } else {
        previewContent.innerHTML = `
          <div style="text-align:center; padding:20px;">
            <i class="fa-solid fa-file" style="font-size:3rem; color:#f9d71c; margin-bottom:10px;"></i>
            <p>Preview not available for this file type</p>
            <p style="font-size:0.8rem; color:#94a0c1;">File: ${file.name}</p>
          </div>
        `;
      }
    });
  }

  // Upload button handler
  if (uploadButton) {
    uploadButton.addEventListener("click", async function () {
      const file = fileInput.files[0];
      if (!file) return;

      overlay.classList.add("active");
      loadingText.textContent = "Uploading to IPFS...";

      const formData = new FormData();
      formData.append("file", file);

      try {
        const { ok, status, json } = await apiJson("/upload", {
          method: "POST",
          body: formData,
        });

        if (!ok) {
          throw new Error(json?.error || "Upload failed");
        }

        // Success
        if (typeof showUploadSuccess === "function") {
          showUploadSuccess(json.cid);
        }

        // Reset form and reload files
        fileInput.value = "";
        uploadButton.disabled = true;
        filePreview.style.display = "none";
        setTimeout(() => window.location.reload(), 1000);
      } catch (error) {
        if (typeof showUploadError === "function") {
          showUploadError(error.message);
        }
      } finally {
        overlay.classList.remove("active");
      }
    });
  }

  // Drag and drop functionality
  if (uploadArea) {
    uploadArea.addEventListener("dragover", (e) => {
      e.preventDefault();
      uploadArea.style.borderColor = "#f9d71c";
      uploadArea.style.background = "rgba(249, 215, 28, 0.1)";
    });

    uploadArea.addEventListener("dragleave", () => {
      uploadArea.style.borderColor = "rgba(249, 215, 28, 0.3)";
      uploadArea.style.background = "transparent";
    });

    uploadArea.addEventListener("drop", (e) => {
      e.preventDefault();
      uploadArea.style.borderColor = "rgba(249, 215, 28, 0.3)";
      uploadArea.style.background = "transparent";

      const files = e.dataTransfer.files;
      if (files.length > 0) {
        fileInput.files = files;
        fileInput.dispatchEvent(new Event("change"));
      }
    });
  }
}

// File management functionality
function initializeFileManagement() {
  // Preview file handler
  document.addEventListener("click", function (e) {
    if (e.target.closest(".preview-btn")) {
      const btn = e.target.closest(".preview-btn");
      const cid = btn.dataset.cid;
      const filename = btn.dataset.filename;

      if (typeof previewCid === "function") {
        previewCid(cid, filename);
      }
    }
  });

  // Delete file handler
  document.addEventListener("click", function (e) {
    if (e.target.closest(".delete-btn")) {
      const btn = e.target.closest(".delete-btn");
      const fileId = btn.dataset.id;
      const filename = btn.dataset.filename;

      if (typeof deleteFile === "function") {
        deleteFile(fileId, filename);
      }
    }
  });

  // CID preview handler
  const previewBtn = document.getElementById("previewBtn");
  const cidInput = document.getElementById("cidInput");

  if (previewBtn && cidInput) {
    previewBtn.addEventListener("click", () => {
      const cid = cidInput.value.trim();
      if (!cid) {
        alert("Please enter a CID");
        return;
      }
      if (typeof previewCid === "function") {
        previewCid(cid);
      }
    });
  }
}

// Initialize when DOM is loaded
document.addEventListener("DOMContentLoaded", function () {
  initializeUpload();
  initializeFileManagement();
});
