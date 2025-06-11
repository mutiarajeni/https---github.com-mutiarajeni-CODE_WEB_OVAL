// upload gambar

let dropArea = document.getElementById("drop-area");
let gambar = document.getElementById("gambar");
let content = dropArea.querySelector(".content");

["dragenter", "dragover", "dragleave", "drop"].forEach((eventName) => {
  dropArea.addEventListener(eventName, preventDefaults, false);
  document.body.addEventListener(eventName, preventDefaults, false);
});

["dragenter", "dragover"].forEach((eventName) => {
  dropArea.addEventListener(eventName, highlight, false);
});

["dragleave", "drop"].forEach((eventName) => {
  dropArea.addEventListener(eventName, unhighlight, false);
});

dropArea.addEventListener("drop", handleDrop, false);
dropArea.addEventListener("click", () => {
  gambar.click();
});

gambar.addEventListener("change", function (e) {
  handleFiles(this.files);
});

function preventDefaults(e) {
  e.preventDefault();
  e.stopPropagation();
}

function highlight(e) {
  dropArea.classList.add("highlight");
}

function unhighlight(e) {
  dropArea.classList.remove("highlight");
}

function handleDrop(e) {
  let dt = e.dataTransfer;
  let files = dt.files;
  handleFiles(files);
}

function handleFiles(files) {
  clearImages();
  if (files.length > 0) {
    previewFile(files[0]);
  }
}

function clearImages() {
  let imgs = dropArea.querySelectorAll("img");
  imgs.forEach((img) => img.remove());
  content.style.display = "flex";
}

function previewFile(file) {
  let reader = new FileReader();
  reader.readAsDataURL(file);
  reader.onloadend = function () {
    let img = document.createElement("img");
    img.src = reader.result;
    dropArea.appendChild(img);
    content.style.display = "none";
  };
}
