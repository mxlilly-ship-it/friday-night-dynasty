import { getAuth, createUserWithEmailAndPassword, signInWithEmailAndPassword } from 'firebase/auth'
import app from './firebase.js'

const auth = getAuth(app)

/** SIGN UP */
export const signUp = (email, password) => {
  return createUserWithEmailAndPassword(auth, email, password)
}

/** LOGIN */
export const login = (email, password) => {
  return signInWithEmailAndPassword(auth, email, password)
}

export { auth }
