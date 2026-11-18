const entryForm = document.querySelector("#entry-composer");
const entryText = entryForm.elements.namedItem("message");
const sectionSelect = entryForm.elements.namedItem("section");
const authorInput = entryForm.elements.namedItem("author");
const attachments = entryForm.elements.namedItem("files");
const selectedFiles = document.querySelector("#entry-selected-files");

function removeAttachment(index) {
  const remaining = new DataTransfer();
  Array.from(attachments.files).forEach((file, position) => {
    if (position !== index) remaining.items.add(file);
  });
  attachments.files = remaining.files;
  updateAttachments();

  const nextItem = selectedFiles.children[index] ?? selectedFiles.lastElementChild;
  (nextItem?.querySelector("button") ?? attachments).focus();
}

function updateAttachments() {
  const items = Array.from(attachments.files, (file, index) => {
    const item = document.createElement("li");
    const name = document.createElement("span");
    name.className = "entry-attachment-name";
    name.textContent = file.name;

    const remove = document.createElement("button");
    remove.className = "entry-attachment-remove";
    remove.type = "button";
    remove.textContent = "×";
    remove.setAttribute("aria-label", `Remove ${file.name}`);
    remove.addEventListener("click", () => removeAttachment(index));

    item.append(name, remove);
    return item;
  });
  selectedFiles.replaceChildren(...items);
  selectedFiles.hidden = items.length === 0;
}

attachments.addEventListener("change", updateAttachments);
window.addEventListener("pageshow", updateAttachments);

function updateAuthorStyle() {
  const name = authorInput.value.trim();
  authorInput.toggleAttribute("data-custom-author", name !== "" && name !== authorInput.defaultValue);
}

authorInput.addEventListener("input", updateAuthorStyle);
window.addEventListener("pageshow", updateAuthorStyle);

if (sectionSelect) {
  entryForm.addEventListener("invalid", (event) => {
    if (!sectionSelect.validity.valueMissing) return;

    event.preventDefault();
    if (event.target === sectionSelect) {
      sectionSelect.setAttribute("aria-invalid", "true");
      sectionSelect.focus();
    }
  }, true);

  sectionSelect.addEventListener("change", () => {
    if (sectionSelect.value) sectionSelect.removeAttribute("aria-invalid");
  });
}

entryText.addEventListener("keydown", (event) => {
  if (event.key !== "Enter" || event.shiftKey || event.isComposing) return;

  event.preventDefault();
  if (!event.repeat) entryForm.requestSubmit();
});
