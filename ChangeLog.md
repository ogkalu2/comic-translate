# Registro delle modifiche di CTkif2.5VL

## [1.0.3] - 2025-03-18

### Correzioni

#### Gestione Font
- Risolto il problema dell'aggiornamento dei font nel dropdown della Home
- Migliorata la comunicazione tra la pagina Settings e la Home
- Implementato il salvataggio automatico delle impostazioni dei font quando vengono modificate
- Ottimizzata l'applicazione delle selezioni font in tempo reale

## [1.0.2] - 2025-03-17

### Nuove funzionalità

#### Gestione Font
- Aggiunta una nuova sezione nella pagina Impostazioni per selezionare i font di sistema da utilizzare
- Implementata funzionalità per visualizzare tutti i font del sistema con checkbox individuali
- Aggiunti pulsanti "Seleziona tutti" e "Deseleziona tutti" per facilitare la gestione dei font
- Il dropdown dei font nella pagina principale ora mostra solo i font selezionati nelle impostazioni
- Migliorata l'anteprima dei font nelle impostazioni utilizzando il font stesso per visualizzarlo

## [1.0.1] - 2025-03-16

### Correzioni e miglioramenti

#### Funzionalità Watermark
- Risolto un errore critico nel `WatermarkItem` che impediva l'aggiunta del watermark all'immagine
- La classe `WatermarkItem` ora eredita correttamente da `QObject` per supportare i segnali
- Corretto il metodo `qpixmap_to_opencv` per gestire correttamente l'oggetto `memoryview` restituito da `bits()`
- Rimossa la funzionalità di tinta colore del watermark per semplificare l'interfaccia
- Risolti problemi di sovrapposizione nei controlli del widget watermark

#### Interfaccia utente
- Migliorato il layout del widget Watermark con controlli posizionati correttamente
- Rimosso pulsante CARICA duplicato nell'interfaccia principale
- Aumentata l'altezza del pannello strumenti per visualizzare meglio tutti i controlli
- Resa più visibile l'anteprima del watermark
