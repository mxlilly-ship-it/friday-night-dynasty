import { getAuth, createUserWithEmailAndPassword, signInWithEmailAndPassword, sendPasswordResetEmail } from 'firebase/auth'
import { getFirebaseApp } from './firebase.js'

function firebaseAuth() {
  return getAuth(getFirebaseApp())
}

/** SIGN UP */
export const signUp = (email, password) => {
  return createUserWithEmailAndPassword(firebaseAuth(), email, password)
}

/** LOGIN */
export const login = (email, password) => {
  return signInWithEmailAndPassword(firebaseAuth(), email, password)
}

/** PASSWORD RESET — sends Firebase reset email */
export const resetPassword = (email) => {
  return sendPasswordResetEmail(firebaseAuth(), email.trim())
}

export function getAuthInstance() {
  return firebaseAuth()
}
