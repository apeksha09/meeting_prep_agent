let calendar;

function setStatus(message) {
  document.getElementById("run-status").textContent = message;
}

function activateTab(targetId) {
  document.querySelectorAll(".tab").forEach((tab) => {
    const active = tab.dataset.target === targetId;
    tab.classList.toggle("is-active", active);
    tab.setAttribute("aria-selected", active ? "true" : "false");
  });

  document.querySelectorAll(".panel").forEach((panel) => {
    panel.classList.toggle("is-active", panel.id === targetId);
  });
}

function renderBriefing(detail) {
  const briefingEl = document.getElementById("briefing-content");
  let rendered = detail.briefing;

  if (window.marked) {
    marked.setOptions({ gfm: true, breaks: true });
    rendered = marked.parse(detail.briefing || "");
  }

  if (window.DOMPurify) {
    rendered = DOMPurify.sanitize(rendered);
    briefingEl.innerHTML = rendered;
  } else {
    briefingEl.textContent = detail.briefing;
  }

  document.getElementById("briefing-title").textContent = detail.title;
  activateTab("panel-briefings");
}

async function fetchBriefing(meetingId) {
  const response = await fetch(`/api/briefings/${meetingId}`);
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || "Briefing not found.");
  }
  return response.json();
}

async function refreshBriefingList() {
  const listEl = document.getElementById("briefing-list");
  listEl.innerHTML = "";

  const response = await fetch("/api/briefings");
  const payload = await response.json();
  const briefings = payload.briefings || [];

  if (!briefings.length) {
    const empty = document.createElement("div");
    empty.className = "briefing-empty";
    empty.textContent = "No briefings yet. Run the agent to generate them.";
    listEl.appendChild(empty);
    return;
  }

  briefings.forEach((item) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "briefing-item";
    button.textContent = `${item.title} (${item.meeting_id})`;
    button.addEventListener("click", () => renderBriefing(item));
    listEl.appendChild(button);
  });
}

async function refreshMeetingsOnCalendar() {
  const response = await fetch("/api/meetings");
  const payload = await response.json();
  const events = payload.events || [];

  calendar.removeAllEvents();
  calendar.addEventSource(events.map((event) => ({
    id: event.id,
    title: event.title,
    start: event.start,
    end: event.end,
    classNames: [event.has_briefing ? "meeting-has-briefing" : "meeting-no-briefing"],
    extendedProps: {
      hasBriefing: event.has_briefing,
      location: event.location,
    },
  })));
}

async function runAgent() {
  const runBtn = document.getElementById("run-agent-btn");
  runBtn.disabled = true;
  setStatus("Running agent and generating briefings...");

  try {
    const response = await fetch("/api/run-agent", { method: "POST" });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || "Unable to run agent.");
    }

    setStatus(payload.message || "Completed.");
    await refreshMeetingsOnCalendar();
    await refreshBriefingList();
  } catch (error) {
    setStatus(`Error: ${error.message}`);
  } finally {
    runBtn.disabled = false;
  }
}

function initCalendar() {
  const calendarEl = document.getElementById("calendar");
  calendar = new FullCalendar.Calendar(calendarEl, {
    initialView: "dayGridMonth",
    headerToolbar: {
      left: "prev,next today",
      center: "title",
      right: "dayGridMonth,timeGridWeek,timeGridDay",
    },
    eventClick: async (info) => {
      const hasBriefing = info.event.extendedProps.hasBriefing;
      if (!hasBriefing) {
        setStatus("This meeting is not clickable yet. Run agent to create briefing.");
        return;
      }

      try {
        const briefing = await fetchBriefing(info.event.id);
        renderBriefing(briefing);
        setStatus(`Showing briefing for ${briefing.title}.`);
      } catch (error) {
        setStatus(`Error: ${error.message}`);
      }
    },
  });

  calendar.render();
}

function initTabs() {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => activateTab(tab.dataset.target));
  });
}

document.addEventListener("DOMContentLoaded", async () => {
  initTabs();
  initCalendar();

  document.getElementById("run-agent-btn").addEventListener("click", runAgent);

  try {
    await refreshMeetingsOnCalendar();
    await refreshBriefingList();
  } catch (error) {
    setStatus(`Error loading dashboard data: ${error.message}`);
  }
});