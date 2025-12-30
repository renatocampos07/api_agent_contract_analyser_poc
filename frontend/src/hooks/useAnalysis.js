import { useState } from 'react';
import api from '../services/api';

const POLLING_INTERVAL = 3000; // 3 segundos

export const useAnalysis = () => {
  const [jobStatus, setJobStatus] = useState('idle');
  const [jobId, setJobId] = useState(null);
  const [report, setReport] = useState(null);
  const [downloadUrl, setDownloadUrl] = useState(null);
  const [error, setError] = useState(null);
  const [pollingIntervalId, setPollingIntervalId] = useState(null);

  const stopPolling = () => {
    if (pollingIntervalId) {
      clearInterval(pollingIntervalId);
      setPollingIntervalId(null);
    }
  };

  const checkJobStatus = async (id) => {
    try {
      const response = await api.get(`/status/${id}`);
      const { status, resultado, download_url } = response.data;
      
      setJobStatus(status);

      if (status === 'complete') {
        setReport(resultado);
        setDownloadUrl(download_url);
        stopPolling();
      } else if (status === 'failed') {
        setError(response.data.resultado || 'A análise falhou.');
        stopPolling();
      }
    } catch (err) {
      setError('Erro ao verificar status.');
      stopPolling();
    }
  };

  const startAnalysis = async (file, useRag) => {
    stopPolling(); // Limpa polls anteriores
    setJobStatus('uploading');
    setError(null);
    setReport(null);
    setDownloadUrl(null);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('use_rag', useRag);

    try {
      const response = await api.post('/iniciar_analise', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      const { job_id, status } = response.data;
      setJobId(job_id);
      setJobStatus(status);

      // Inicia o polling
      const intervalId = setInterval(() => {
        checkJobStatus(job_id);
      }, POLLING_INTERVAL);
      setPollingIntervalId(intervalId);

    } catch (err) {
      setError('Erro ao iniciar a análise.');
      setJobStatus('idle');
    }
  };

  return { jobStatus, report, downloadUrl, error, startAnalysis };
};