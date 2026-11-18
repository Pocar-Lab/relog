const sectionHistory = document.querySelector("#section-entry-history");
const sectionEntryText = document.querySelector("#entry-composer-text");
const replyTarget = sectionEntryText.form.elements.namedItem("reply_to");
const replyReference = document.querySelector("#entry-reply-reference");
const earlierEntries = document.querySelector("#earlier-entries");
const historyStatus = document.querySelector("#log-history-status");

sectionHistory.addEventListener("click", (event) => {
  const referenceButton = event.target.closest("[data-entry-reference]");
  if (referenceButton) {
    const reference = referenceButton.dataset.entryReference;
    if (replyTarget) {
      replyTarget.value = reference;
      replyReference.textContent = `Re: #${reference}`;
    } else {
      const prefix = `Re: #${reference}\n\n`;
      const existingReference = sectionEntryText.value.match(/^Re: #[0-9]+(?:\n{1,2}|$)/);
      sectionEntryText.setRangeText(prefix, 0, existingReference ? existingReference[0].length : 0, "end");
    }
    sectionEntryText.focus();
    return;
  }

  const crossoutButton = event.target.closest(".log-crossout");
  if (crossoutButton) {
    document.getElementById(crossoutButton.getAttribute("aria-controls")).showModal();
  }
});

async function showEarlierEntries() {
  if (earlierEntries.getAttribute("aria-busy") === "true") return;

  const { earlierUrl, earlierDate } = earlierEntries.dataset;
  earlierEntries.setAttribute("aria-busy", "true");
  historyStatus.textContent = "";

  try {
    const response = await fetch(earlierUrl);
    if (!response.ok) throw new Error("Could not load entries");

    const page = new DOMParser().parseFromString(await response.text(), "text/html");
    const loadedHistory = page.querySelector("#section-entry-history");
    if (!loadedHistory) throw new Error("The entry history was unavailable");

    const loadedDay = loadedHistory.firstElementChild;
    if (!loadedDay) {
      historyStatus.textContent = `No entries on ${earlierDate}.`;
    } else if (!document.getElementById(loadedDay.id)) {
      sectionHistory.prepend(loadedDay);
      document.querySelector("#log-history-empty")?.remove();
      historyStatus.textContent = `Added entries from ${earlierDate}.`;
    }

    const nextDay = page.querySelector("#earlier-entries");
    if (nextDay) {
      earlierEntries.dataset.earlierUrl = nextDay.dataset.earlierUrl;
      earlierEntries.dataset.earlierDate = nextDay.dataset.earlierDate;
      earlierEntries.title = nextDay.title;
    } else {
      earlierEntries.disabled = true;
    }
  } catch {
    historyStatus.textContent = "Couldn’t load earlier entries. Try again.";
  } finally {
    earlierEntries.removeAttribute("aria-busy");
  }
}

earlierEntries?.addEventListener("click", showEarlierEntries);
