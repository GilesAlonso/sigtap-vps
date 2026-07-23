#!/bin/bash
# ==============================================================================
# Script de Instalação e Configuração do GoAccess para Monitoramento do SIGTAP
# ==============================================================================

echo "=== 1. Instalando o GoAccess no Ubuntu ==="
sudo apt update
sudo apt install -y goaccess mmdb-bin

echo ""
echo "=== 2. Como usar o GoAccess na VPS ==="
echo "a) Visualizar no Terminal (Tempo Real interativo):"
echo "   goaccess /home/ubuntu/Sigtap/access.log --log-format=COMBINED"
echo ""
echo "b) Gerar um relatório HTML estático:"
echo "   goaccess /home/ubuntu/Sigtap/access.log --log-format=COMBINED -o /home/ubuntu/Sigtap/static_report.html"
echo ""
echo "c) Gerar relatório HTML em tempo real (Painel Web em tempo real):"
echo "   goaccess /home/ubuntu/Sigtap/access.log --log-format=COMBINED -o /home/ubuntu/Sigtap/templates/stats.html --real-time-html"
echo "=============================================================================="
