import { theme } from "../theme";
import { useEffect, useState } from "react";
import {
  getEvents,
  createEvent,
  updateEvent,
  deleteEvent,
} from "../services/eventsApi";
import { getUsers } from "../services/usersApi";

/* ---------- Helper Functions ---------- */

function getDaysInMonth(year, month) {
  return new Date(year, month + 1, 0).getDate();
}

function getFirstDayOfMonth(year, month) {
  return new Date(year, month, 1).getDay();
}

function groupEventsByDay(events, year, month) {
  const map = {};

  events.forEach((event) => {
    const [y, m, d] = event.start_date.split("-").map(Number);
    if (y === year && m === month + 1) {
      if (!map[d]) map[d] = [];
      map[d].push(event);
    }
  });

  return map;
}

/* ---------- Component ---------- */

function CalendarPlaceholder() {
  const today = new Date();

  const [events, setEvents] = useState([]);
  const [users, setUsers] = useState([]);

  const [currentYear, setCurrentYear] = useState(today.getFullYear());
  const [currentMonth, setCurrentMonth] = useState(today.getMonth());

  const [showAddEvent, setShowAddEvent] = useState(false);
  const [selectedEvent, setSelectedEvent] = useState(null);

  const [title, setTitle] = useState("");
  const [date, setDate] = useState("");
  const [ownerId, setOwnerId] = useState(1);

  const [touchStartX, setTouchStartX] = useState(null);
  const [touchEndX, setTouchEndX] = useState(null);

  const [isAnimating, setIsAnimating] = useState(false);

  const todayDate = today.getDate();
  const isCurrentMonth =
    currentYear === today.getFullYear() &&
    currentMonth === today.getMonth();

  const eventsByDay = groupEventsByDay(events, currentYear, currentMonth);

  /* ---------- Load Data ---------- */

  useEffect(() => {
    async function loadAll() {
      try {
        const [eventsData, usersData] = await Promise.all([
          getEvents(),
          getUsers(),
        ]);

        setEvents(eventsData);
        setUsers(usersData);
      } catch (error) {
        console.error(error);
      }
    }

    loadAll();
  }, []);

  /* ---------- Swipe Navigation ---------- */

  function handleTouchStart(e) {
    setTouchStartX(e.touches[0].clientX);
  }

  function handleTouchMove(e) {
    setTouchEndX(e.touches[0].clientX);
  }

  function handleTouchEnd() {
    if (touchStartX === null || touchEndX === null) return;

    const deltaX = touchStartX - touchEndX;
    const threshold = 60;

    if (Math.abs(deltaX) > threshold) {
      if (deltaX > 0) {
        goToNextMonth();
      } else {
        goToPreviousMonth();
      }
    }

    setTouchStartX(null);
    setTouchEndX(null);
  }

  function goToPreviousMonth() {
    setIsAnimating(true);

    setTimeout(() => {
      setCurrentMonth((prevMonth) => {
        if (prevMonth === 0) {
          setCurrentYear((prevYear) => prevYear - 1);
          return 11;
        }
        return prevMonth - 1;
      });

      setIsAnimating(false);
    }, 120);
  }

  function goToNextMonth() {
    setIsAnimating(true);

    setTimeout(() => {
      setCurrentMonth((prevMonth) => {
        if (prevMonth === 11) {
          setCurrentYear((prevYear) => prevYear + 1);
          return 0;
        }
        return prevMonth + 1;
      });

      setIsAnimating(false);
    }, 120);
  }

  /* ---------- CRUD ---------- */

  async function handleAddEvent() {
    try {
      await createEvent({
        title,
        start_date: date,
        end_date: date,
        owner_id: ownerId,
        all_day: true,
        type: "manual",
      });

      setEvents(await getEvents());
      setTitle("");
      setDate("");
      setShowAddEvent(false);
    } catch (error) {
      console.error(error);
    }
  }

  async function handleUpdateEvent() {
    try {
      await updateEvent(selectedEvent);
      setEvents(await getEvents());
      setSelectedEvent(null);
    } catch (error) {
      console.error(error);
    }
  }

  async function handleDeleteEvent() {
    try {
      await deleteEvent(selectedEvent.id);
      setEvents(await getEvents());
      setSelectedEvent(null);
    } catch (error) {
      console.error(error);
    }
  }

  const firstDay = getFirstDayOfMonth(currentYear, currentMonth);
  const daysInMonth = getDaysInMonth(currentYear, currentMonth);
  const totalCells = firstDay + daysInMonth;
  const rowCount = Math.ceil(totalCells / 7);

  /* ---------- Render ---------- */

  return (
    <>
      {/* Floating Month Title */}
      <h2
        style={styles.monthTitle}
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTouchEnd}
      >
        {new Date(currentYear, currentMonth).toLocaleString("default", {
          month: "long",
        })}{" "}
        {currentYear}
      </h2>

      {/* Calendar Panel */}
      <div style={styles.container}>
        <button
          style={styles.addEventButton}
          onClick={() => setShowAddEvent(true)}
        >
          + Add Event
        </button>

        <div style={styles.weekdays}>
          {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((day) => (
            <div key={day} style={styles.weekday}>
              {day}
            </div>
          ))}
        </div>

        <div
          style={{
            ...styles.gridWrapper,
            opacity: isAnimating ? 0 : 1,
            transform: isAnimating
              ? "translateX(8px)"
              : "translateX(0px)",
          }}
        >
          <div
            style={{
              ...styles.grid,
              gridTemplateRows: `repeat(${rowCount}, 1fr)`,
            }}
          >
            {Array(firstDay)
              .fill(null)
              .map((_, i) => (
                <div key={`empty-${i}`} />
              ))}

            {Array(daysInMonth)
              .fill(null)
              .map((_, i) => {
                const day = i + 1;
                const dayEvents = eventsByDay[day] || [];

                return (
                  <div
                    key={day}
                    style={{
                      ...styles.cell,
                      ...(isCurrentMonth &&
                      day === todayDate
                        ? styles.todayCell
                        : {}),
                    }}
                  >
                    <div style={styles.dayNumber}>
                      {day}
                    </div>

                    {dayEvents.map((event) => {
                      const owner = users.find(
                        (u) => u.id === event.owner_id
                      );

                      return (
                        <div
                          key={event.id}
                          onClick={() =>
                            setSelectedEvent(event)
                          }
                          style={{
                            ...styles.event,
                            backgroundColor:
                              owner?.color || "#dbeafe",
                          }}
                        >
                          {event.title}
                        </div>
                      );
                    })}
                  </div>
                );
              })}
          </div>
        </div>

        {/* Add Modal */}
        {showAddEvent && (
          <div style={styles.modalOverlay}>
            <div style={styles.modal}>
              <h3>Add Event</h3>

              <input
                placeholder="Title"
                value={title}
                onChange={(e) =>
                  setTitle(e.target.value)
                }
                style={styles.input}
              />

              <input
                type="date"
                value={date}
                onChange={(e) =>
                  setDate(e.target.value)
                }
                style={styles.input}
              />

              <select
                value={ownerId}
                onChange={(e) =>
                  setOwnerId(Number(e.target.value))
                }
                style={styles.input}
              >
                {users.map((user) => (
                  <option
                    key={user.id}
                    value={user.id}
                  >
                    {user.name}
                  </option>
                ))}
              </select>

              <div style={styles.modalActions}>
                <button
                  onClick={handleAddEvent}
                  style={styles.saveButton}
                >
                  Save
                </button>
                <button
                  onClick={() =>
                    setShowAddEvent(false)
                  }
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Edit Modal */}
        {selectedEvent && (
          <div style={styles.modalOverlay}>
            <div style={styles.modal}>
              <h3>Edit Event</h3>

              <input
                value={selectedEvent.title}
                onChange={(e) =>
                  setSelectedEvent({
                    ...selectedEvent,
                    title: e.target.value,
                  })
                }
                style={styles.input}
              />

              <input
                type="date"
                value={selectedEvent.start_date}
                onChange={(e) =>
                  setSelectedEvent({
                    ...selectedEvent,
                    start_date: e.target.value,
                    end_date: e.target.value,
                  })
                }
                style={styles.input}
              />

              <div style={styles.modalActions}>
                <button
                  onClick={handleUpdateEvent}
                  style={styles.saveButton}
                >
                  Save
                </button>
                <button
                  onClick={handleDeleteEvent}
                  style={styles.deleteButton}
                >
                  Delete
                </button>
                <button
                  onClick={() =>
                    setSelectedEvent(null)
                  }
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </>
  );
}

/* ---------- Styles ---------- */

const styles = {
  monthTitle: {
    fontSize: theme.font.xlarge,
    fontWeight: "600",
    color: theme.colors.textPrimary,
    textAlign: "center",
    marginTop: theme.spacing.lg,
    marginBottom: theme.spacing.md,
  },

  container: {
    height: "75vh",
    width: "100%",
    maxWidth: "1200px",
    margin: "0 auto",
    display: "flex",
    flexDirection: "column",
    backgroundColor: theme.colors.panel,
    borderRadius: theme.radius.lg,
    padding: theme.spacing.lg,
    boxShadow: theme.shadow.soft,
  },

  addEventButton: {
    alignSelf: "flex-end",
    marginBottom: theme.spacing.md,
  },

  weekdays: {
    display: "grid",
    gridTemplateColumns: "repeat(7, 1fr)",
    marginBottom: theme.spacing.sm,
  },

  weekday: {
    textAlign: "center",
    fontWeight: "500",
    color: theme.colors.textSecondary,
  },

  gridWrapper: {
    flex: 1,
    transition: "all 150ms ease",
    display: "flex",
  },

  grid: {
    flex: 1,
    display: "grid",
    gridTemplateColumns: "repeat(7, minmax(0, 1fr))",
    gap: "12px",
  },

  cell: {
    display: "flex",
    flexDirection: "column",
    borderRadius: "12px",
    padding: "10px",
    backgroundColor: "#f9fafb",
  },

  todayCell: {
    border: "2px solid #2563eb",
    backgroundColor: "#eff6ff",
  },

  dayNumber: {
    fontSize: theme.font.medium,
    fontWeight: "600",
    color: theme.colors.textPrimary,
  },

  event: {
    marginTop: "6px",
    padding: "6px 8px",
    fontSize: "0.9rem",
    borderRadius: "8px",
    color: theme.colors.textPrimary,
    cursor: "pointer",
  },

  modalOverlay: {
    position: "fixed",
    inset: 0,
    backgroundColor: "rgba(0,0,0,0.4)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 1000,
  },

  modal: {
    backgroundColor: "white",
    padding: "20px",
    borderRadius: "12px",
    width: "90%",
    maxWidth: "400px",
  },

  input: {
    display: "block",
    width: "100%",
    marginBottom: "12px",
    padding: "8px",
    fontSize: "1rem",
  },

  modalActions: {
    display: "flex",
    justifyContent: "space-between",
  },

  saveButton: {
    backgroundColor: theme.colors.accent,
    color: "white",
    border: "none",
    padding: "8px 16px",
    borderRadius: "6px",
    cursor: "pointer",
  },

  deleteButton: {
    backgroundColor: "#dc2626",
    color: "white",
    border: "none",
    padding: "8px 16px",
    borderRadius: "6px",
    cursor: "pointer",
  },
};

export default CalendarPlaceholder;