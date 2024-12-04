// Handle contract details
const handleDetails = {
    init() {
        // Handle detail button clicks using event delegation
        document.addEventListener('click', (event) => {
            const button = event.target.closest('.botao-detalhes');
            if (button) {
                console.log('Button clicked:', button);
                const contratoData = button.getAttribute('data-contrato');
                console.log('Raw contrato data:', contratoData);
                
                if (contratoData) {
                    try {
                        const dados = JSON.parse(contratoData);
                        console.log('Parsed data:', dados);
                        if (dados.CCB) {
                            window.location.href = `/resultado?ccb=${dados.CCB}`;
                        } else {
                            console.error('CCB não encontrado nos dados');
                        }
                    } catch (error) {
                        console.error('Erro ao processar dados do contrato:', error);
                        console.error('Dados recebidos:', contratoData);
                    }
                } else {
                    console.error('Nenhum dado encontrado no botão');
                }
            }
        });
    }
};

// Initialize when document is ready
document.addEventListener('DOMContentLoaded', () => {
    handleDetails.init();
    console.log('Details handler initialized');
});