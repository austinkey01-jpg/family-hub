import CalendarPlaceholder from "./components/CalendarPlaceholder";
import { theme } from "./theme";

function AppLayout() {
  return (
    <div style={styles.appContainer}>
      {/* Top Header */}
      <header style={styles.header}>
        <h1 style={styles.title}>Family Hub</h1>
        <div style={styles.profileCircle}>👤</div>
      </header>

      {/* Main Content Area */}
      <main style={styles.main}>
        <div style={styles.monthWrapper}>
            <CalendarPlaceholder />
        </div>
    </main>
    </div>
  );
}

const styles = {
  appContainer: {
  height: "100vh",
  width: "100%",
  display: "flex",
  flexDirection: "column",
  backgroundColor: "#d1dbeb",
},

  monthWrapper: {
  width: "100%",
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
},

  header: {
    height: "70px",
    backgroundColor: "#ffffff",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "0 24px",
    borderBottom: "1px solid #e5e7eb",
  },

  title: {
    fontSize: "1.4rem",
    fontWeight: "600",
    color: "#111",
  },

  profileCircle: {
    width: "38px",
    height: "38px",
    borderRadius: "50%",
    backgroundColor: "#e5e7eb",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    cursor: "pointer",
  },

  main: {
  flex: 1,
  display: "flex",
  flexDirection: "column",
  minHeight: 0,
},
};

export default AppLayout;