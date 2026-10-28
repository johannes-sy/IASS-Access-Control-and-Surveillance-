(function(){const img=document.querySelector('#primaryVideo');if(!img)return;img.addEventListener('error',()=>{const w=document.querySelector('#cameraWaiting');if(w)w.style.display='flex'});})();
