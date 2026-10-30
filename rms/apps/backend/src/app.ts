import express from 'express';
import { loadResumeSeed } from './data/resumeStore';
import { candidatesRouter } from './routes/candidates';

loadResumeSeed();

export const app = express();

app.use(express.json());
app.use('/api/candidates', candidatesRouter);
