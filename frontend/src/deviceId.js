/** Stable browser device id for the 3-device account limit. */
export function getOrCreateDeviceId() {
  const key = 'fnd_device_id'
  let id = localStorage.getItem(key)
  if (!id) {
    id = crypto.randomUUID()
    localStorage.setItem(key, id)
  }
  return id
}
