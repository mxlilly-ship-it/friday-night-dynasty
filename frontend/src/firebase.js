import { initializeApp } from 'firebase/app'
import { getAnalytics, isSupported } from 'firebase/analytics'

const firebaseConfig = {
  apiKey: 'AIzaSyD0mACh_s3cuJOInpe6J0alc-NfIRNdAk8',
  authDomain: 'friday-night-dynasty.firebaseapp.com',
  projectId: 'friday-night-dynasty',
  storageBucket: 'friday-night-dynasty.firebasestorage.app',
  messagingSenderId: '926329972325',
  appId: '1:926329972325:web:ad096675869ed76257c88c',
  measurementId: 'G-H102NJ79KB',
}

const app = initializeApp(firebaseConfig)

/** Analytics only in the browser (Vite dev/build); null during SSR/tests. */
let analytics = null
if (typeof window !== 'undefined') {
  isSupported().then((supported) => {
    if (supported) analytics = getAnalytics(app)
  })
}

export { analytics }
export default app
