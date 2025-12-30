import React, { useState } from 'react';

export const AnalysisReport = ({ report, downloadUrl }) => {
  const [selectedClauseId, setSelectedClauseId] = useState(
    report.clausulas.length > 0 ? report.clausulas[0].id_clausula : null
  );

  const selectedClause = report.clausulas.find(c => c.id_clausula === selectedClauseId);
  const errorCount = (errors) => errors ? errors.length : 0;

  return (
    <div className="report-container">
      
      {/* PAINEL 1: GLOBAL */}
      <div className="report-global">
        <h3>Análise Concluída</h3>
        <a href={`${import.meta.env.VITE_API_URL.replace('/api', '')}${downloadUrl}`} 
           download 
           className="download-btn">
          Baixar .docx Revisado
        </a>
        {report.erros_globais && report.erros_globais.length > 0 && (
          <div className="global-errors">
            <h4>Alertas Globais:</h4>
            {report.erros_globais.map((err, idx) => (
              <div key={idx} className="error-card global">
                <strong>[{err.id_regra}]</strong> {err.comentario}
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="report-main-content">
        {/* PAINEL 2: LISTA DE CLÁUSULAS */}
        <div className="report-sidebar">
          <h4>Cláusulas Encontradas</h4>
          <ul>
            {report.clausulas.map(clausula => (
              <li 
                key={clausula.id_clausula}
                className={clausula.id_clausula === selectedClauseId ? 'active' : ''}
                onClick={() => setSelectedClauseId(clausula.id_clausula)}
              >
                {errorCount(clausula.erros_encontrados) > 0 ? '🔴' : '🟢'}
                {clausula.titulo} 
                ({errorCount(clausula.erros_encontrados)} erros)
              </li>
            ))}
          </ul>
        </div>

        {/* PAINEL 3: DETALHE DA CLÁUSULA */}
        <div className="report-detail">
          {selectedClause ? (
            <>
              <h3>{selectedClause.titulo}</h3>
              
              <h4>Erros Encontrados na Cláusula:</h4>
              {selectedClause.erros_encontrados.length > 0 ? (
                selectedClause.erros_encontrados.map((err, idx) => (
                  <div key={idx} className="error-card">
                    <strong>[{err.id_regra}]</strong> {err.comentario}
                    <p className="error-quote">Trecho: "{err.trecho_exato}"</p>
                  </div>
                ))
              ) : (
                <p>Nenhum erro encontrado nesta cláusula.</p>
              )}
              
              <hr />
              <h4>Texto Original da Cláusula:</h4>
              <pre className="clausula-text">
                {selectedClause.texto_original}
              </pre>
            </>
          ) : (
            <p>Selecione uma cláusula para ver os detalhes.</p>
          )}
        </div>
      </div>
    </div>
  );
};