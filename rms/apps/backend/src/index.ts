import { app } from './app';

const PORT = 3001;

app.listen(PORT, () => {
  console.log(`RMS backend listening on http://localhost:${PORT}`);
});
