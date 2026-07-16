# Contingência Operacional de Alta Disponibilidade

**Garantindo zero tempo de inatividade para secretarias de saúde durante falhas em sistemas federais externos.**

## O Contexto
Na Secretaria de Estado da Saúde do Espírito Santo (SESA), as operações administrativas diárias dependem fortemente da plataforma federal SIGTAP (Sistema de Gerenciamento da Tabela de Procedimentos). Este banco de dados unificado contém códigos críticos, regras e parâmetros financeiros para processamento de faturamento, cotas e procedimentos de saúde.

## O Gargalo Operacional
Por ser um sistema federal centralizado acessado nacionalmente, o SIGTAP sofre frequentemente com instabilidade imprevisível, lentidão severa e quedas completas de servidor. Quando o site oficial sai do ar, as equipes internas da SESA ficam essencialmente paralisadas. Sem acesso a códigos de procedimentos e regras de validação, os fluxos de trabalho da administração regional de saúde são interrompidos, criando grandes acúmulos administrativos e atrasando operações críticas.

## A Abordagem de Engenharia de Sistemas
Para isolar o departamento estadual de falhas federais, projetamos um Plano de Continuidade de Negócios (BCP) centrado em um sistema espelho resiliente.

- **Espelho de Alta Disponibilidade**: Desenvolvemos um aplicativo espelho independente e leve usando Python e Flask, hospedado de forma segura em um ambiente de servidor separado.
- **Sincronização de Dados**: O sistema armazena e disponibiliza exatamente os dados da tabela unificada exigidos pelas equipes da SESA, estruturados para consultas mais rápidas do que a interface federal legada, utilizando processamento automatizado via SQLite.
- **Transição Sem Atritos**: Projetamos uma interface intuitiva e instantaneamente acessível para a qual a equipe administrativa pode migrar no momento em que o sistema federal sofre inatividade, exigindo zero retreinamento.

## O Resultado
A implementação garantiu 100% de continuidade operacional para a equipe da SESA. Ao tratar as dependências externas como um risco conhecido e projetar um sistema de fallback confiável, eliminamos completamente as horas de tempo ocioso e a paralisia do fluxo de trabalho causadas anteriormente por falhas no servidor federal. A equipe agora opera com total autonomia e resiliência.

---
### Stack Tecnológico
- **Backend:** Python, Flask, SQLite
- **Frontend:** HTML5, Vanilla JavaScript, CSS3
- **Pipelines de Dados:** Extração e normalização automatizada de arquivos ZIP hospedados no DATASUS via serviço background em `systemd`.
