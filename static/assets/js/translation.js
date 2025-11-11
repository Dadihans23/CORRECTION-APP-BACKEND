function updateButtonVisibility() {
    var outputText = document.getElementById("outputText").innerText;
    var buttonsContainer = document.getElementById("buttonsContainer");
    var buttons = buttonsContainer.getElementsByTagName("button");

    
    if (!outputElement || !buttonsContainer) {
        // Évite l'erreur si les éléments ne sont pas encore dans le DOM
        return;
    }
    
    if (outputText.trim() !== "") {
        for (var i =  0; i < buttons.length; i++) {
            buttons[i].style.visibility = "visible";
        }
    } else {
        for (var i =  0; i < buttons.length; i++) {
            buttons[i].style.visibility = "hidden";
        }
    }
}

// Appeler la fonction pour initialiser la visibilité du bouton
updateButtonVisibility();
// Fonction pour gérer la saisie utilisateur et déclencher la traduction
function translateUserInput() {

  let inputText = document.getElementById('inputText').value;

  inputText = inputText.trimStart();
  inputText = inputText.trimEnd();

  const selectedLanguage = document.getElementById('selectLanguage').value;


  if (inputText !== '' && selectedLanguage !== '') {

    // Appeler fonction de traduction
    translateText(inputText, selectedLanguage);

  } else {

    // Afficher message d'erreur 
    const outputText = document.getElementById('outputText');
    outputText.innerHTML = `
      <p style="color:red;">
        Veuillez saisir du texte et sélectionner une langue avant de traduire.
      </p>
    `;
    updateButtonVisibility();


  }

}

// Fonction pour traduire le texte
function translateText(inputText, selectedLanguage) {
    const myHeaders = new Headers();
    myHeaders.append("Content-Type", "application/json");

    const raw = JSON.stringify({
        "message": inputText,
        "target_language": selectedLanguage
    });

    const requestOptions = {
        method: "POST",
        headers: myHeaders,
        body: raw,
        redirect: "follow"
    };

    return fetch("https://projets.expeditalagbe.com/flask_lang_api/translate", requestOptions)
        .then((response) => response.json())
        .then((result) => {
            // Vérifiez si le statut est 'success' avant d'afficher les informations de traduction
            if (result.status === 'success') {
                const outputText = document.getElementById('outputText');
                outputText.innerHTML = `
                    <p text-align: justify;> ${result.translated_text}</p>
                `;

                const sourceLanguageElement = document.getElementById('sourceLanguage');
                sourceLanguageElement.textContent = `langue Source: ${result.source_language_name}`;
                updateButtonVisibility();

            } else {
                console.log(result);
                // Affichez un message d'erreur si le statut n'est pas 'success'
                console.error(result.message);
                const errorMessage = getErrorMessage(result.message);
                const outputText = document.getElementById('outputText');
                outputText.innerHTML = `
                    <p style="color:red;">${errorMessage}</p>
                `;
                updateButtonVisibility();

            }
        })
        .catch((error) => {
            console.error(error);
            const errorMessage = getErrorMessage('general_error');
            const outputText = document.getElementById('outputText');
            outputText.innerHTML = `
                <p style="color:red;">${errorMessage}</p>
            `;
            updateButtonVisibility();

        });
}

// Fonction pour obtenir le message d'erreur approprié
function getErrorMessage(key) {
    const errorMessages = {
        'general_error': 'Un problème s\'est produit. Veuillez réessayer.',
        'custom_error': 'Une erreur personnalisée s\'est produite.', // Nouveau message d'erreur
        // Ajoutez d'autres messages d'erreur au besoin
    };

    return errorMessages[key] || 'Une erreur inconnue s\'est produite.';
}


async function copyToClipboard() {

  const outputText = document.getElementById('outputText');
  let textToCopy = outputText.textContent;

  // Supprimer espaces au début et à la fin
  textToCopy = textToCopy.trim();

  const textarea = document.createElement('textarea');
  textarea.value = textToCopy;

  document.body.appendChild(textarea);

  textarea.select();

  await navigator.clipboard.writeText(textarea.value);

  document.body.removeChild(textarea);
  
  alert('Texte copié dans le presse-papiers!');

}






//  fonctions pour gérer  la lecture de la traduction

function speakText() {
    const outputText = document.getElementById('outputText').innerText;
    const synth = window.speechSynthesis;
    const utterance = new SpeechSynthesisUtterance(outputText);
    synth.speak(utterance);
}