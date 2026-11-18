const registrationUsername = document.querySelector("#account-identifier");

function withoutWhitespace(value) {
  return value.replace(/\s/g, "");
}

registrationUsername.addEventListener("beforeinput", (event) => {
  if (!event.isComposing && event.data && !withoutWhitespace(event.data)) {
    event.preventDefault();
  }
});

function removeUsernameSpaces(event) {
  if (event.isComposing) return;

  const { value, selectionStart, selectionEnd, selectionDirection } = registrationUsername;
  const cleaned = withoutWhitespace(value);
  if (cleaned === value) return;

  registrationUsername.value = cleaned;
  registrationUsername.setSelectionRange(
    withoutWhitespace(value.slice(0, selectionStart)).length,
    withoutWhitespace(value.slice(0, selectionEnd)).length,
    selectionDirection,
  );
}

registrationUsername.addEventListener("input", removeUsernameSpaces);
registrationUsername.addEventListener("compositionend", removeUsernameSpaces);
