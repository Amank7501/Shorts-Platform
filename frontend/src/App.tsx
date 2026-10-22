import { useEffect, useState } from 'react'

function App() {
  const [backend, setBackend] = useState('checking...')

  useEffect(() => {
    fetch('/api/health')
      .then((r) => r.json())
      .then((d) => setBackend(d.status))
      .catch(() => setBackend('unreachable'))
  }, [])

  return (
    <main style={{ padding: 24 }}>
      <h1>Shorts Platform</h1>
      <p>Backend: {backend}</p>
    </main>
  )
}

export default App
