export async function getUsers() {
  const response = await fetch("http://127.0.0.1:8000/users");
  return response.json();
}
