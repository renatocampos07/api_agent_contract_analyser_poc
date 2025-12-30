import React, { useState } from 'react';
import { UploadForm } from './components/UploadForm';
import { AnalysisReport } from './components/AnalysisReport';
import { useAnalysis } from './hooks/useAnalysis';
import './index.css';

function App() {
  const { 
    jobStatus, 
    report, 
    downloadUrl, 
    startAnalysis, 
    error 
  } = useAnalysis();
  
  const [file, setFile] = useState(null);
  const [useRag, setUseRag] = useState(false);

  const handleSubmit = () => {
    if (file) {
      startAnalysis(file, useRag);
    }
  };

  return (
    <div className="container">
      <h1>Revisor de Contrato</h1>
      
      {(!jobStatus || jobStatus === 'idle') && (
        <UploadForm 
          onFileChange={setFile}
          onRagChange={setUseRag}
          onSubmit={handleSubmit}
          file={file}
          useRag={useRag}
        />
      )}
      
      {jobStatus && jobStatus !== 'idle' && jobStatus !== 'complete' && (
        <div className="loading">
          <h2>Analisando seu documento...</h2>
          <p>Status: {jobStatus}</p>
          <div className="spinner"></div>
        </div>
      )}

      {error && <div className="error-box">Erro: {error}</div>}

      {jobStatus === 'complete' && report && (
        <AnalysisReport 
          report={report} 
          downloadUrl={downloadUrl} 
        />
      )}
    </div>
  );
}

export default App;