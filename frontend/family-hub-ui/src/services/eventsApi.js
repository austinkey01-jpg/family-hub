const API_BASE = "http://10.0.0.23:8000";

export async function getEvents() {
  const response = await fetch(`${API_BASE}/events`);
  return response.json();
}

export async function createEvent(event) {
  const response = await fetch(`${API_BASE}/events`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(event),
  });

  if (!response.ok) {
    throw new Error("Failed to create event");
  }

  return response.json();
}

export async function updateEvent(event) {
  const response = await fetch(`${API_BASE}/events/${event.id}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(event),
  });

  if (!response.ok) {
    throw new Error("Failed to update event");
  }

  return response.json();
}

export async function deleteEvent(eventId) {
  const response = await fetch(`${API_BASE}/events/${eventId}`, {
    method: "DELETE",
  });

  if (!response.ok) {
    throw new Error("Failed to delete event");
  }
}

export async function getUsers() {
  const response = await fetch(`${API_BASE}/users`);
  return response.json();
}