# SIGTAP - Contingência Operacional de Alta Disponibilidade

**Garantindo resiliência e zero tempo de inatividade durante falhas em sistemas federais externos.**

## O Contexto
As operações administrativas e de faturamento em saúde pública dependem fortemente da plataforma federal SIGTAP (Sistema de Gerenciamento da Tabela de Procedimentos). Este banco de dados unificado contém códigos críticos, regras e parâmetros financeiros para o processamento de cotas, faturamentos e auditorias em saúde.

## O Desafio Tecnológico
Por ser um sistema centralizado acessado nacionalmente, a interface web oficial do SIGTAP sofre frequentemente com instabilidade imprevisível, lentidão severa e quedas de servidor. Quando o site oficial sai do ar, as equipes de regulação e administração em saúde ficam paralisadas. Sem acesso ágil e confiável aos códigos de procedimentos e regras de validação, os fluxos de trabalho são interrompidos, gerando graves gargalos operacionais.

## A Solução de Engenharia
Para isolar as operações dessas falhas na infraestrutura federal, foi arquitetado um sistema espelho focado em alta disponibilidade e alta performance.

- **Espelho de Alta Disponibilidade**: Desenvolvimento de uma aplicação web independente utilizando Python e Flask, garantindo infraestrutura isolada e resiliência contínua.
- **Sincronização de Dados Automática**: O sistema conecta-se ativamente aos servidores FTP do DATASUS para extrair os dados brutos oficiais, convertendo gigabytes de arquivos legados de texto posicional para um robusto banco de dados relacional SQLite local.
- **Performance e Interface Refinada**: Projetamos um dashboard de consulta de dados ultrarrápido utilizando filtragem avançada via AJAX, substituindo formulários antigos por interfaces dinâmicas, limpas e que permitem seleção múltipla, resolvendo limitações crônicas da plataforma oficial.

## O Resultado
A implementação assegura continuidade operacional ininterrupta para equipes de saúde. Ao tratar as dependências de terceiros como um risco técnico conhecido e desenvolver um fallback inteligente, o sistema garante imunidade completa contra o tempo ocioso provocado pelas quedas do servidor federal, proporcionando pesquisas quase instantâneas e autonomia total.

---
### Stack Tecnológico
- **Backend:** Python, Flask, SQLite
- **Frontend:** HTML5, Vanilla JavaScript, CSS3
- **Data Pipeline:** Extração, transformação e carga (ETL) automatizada dos pacotes ZIP do FTP do DATASUS, gerenciada via agendadores nativos do Linux (`systemd`).
