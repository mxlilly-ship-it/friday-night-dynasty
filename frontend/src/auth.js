import { getAuth, createUserWithEmailAndPassword, signInWithEmailAndPassword } from 'firebase/auth'
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

export function getAuthInstance() {
  return firebaseAuth()
}
