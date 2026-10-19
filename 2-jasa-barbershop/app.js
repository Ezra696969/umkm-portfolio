const SVC=[
["💈","Potong Rambut","Termasuk cuci & styling","30.000"],
["🪒","Cukur Jenggot","Handuk hangat, razor","20.000"],
["✂️","Potong + Cukur","Paling banyak dipilih","45.000"],
["🧴","Hair Coloring","Mulai dari, tergantung warna","120.000"],
["💆","Creambath & Pijat","30 menit","35.000"],
["👦","Potong Anak","Usia di bawah 12 tahun","25.000"]];
document.getElementById('svc').innerHTML=SVC.map(s=>`<div class="s"><i>${s[0]}</i><div><b>${s[1]}</b><small>${s[2]}</small></div><span class="p">${s[3].replace(/^/,'Rp')}</span></div>`).join('');
const T=[
["Hasilnya rapi, tukangnya ramah dan tidak banyak basa-basi. Langganan sejak awal buka.","Dimas, mahasiswa"],
["Booking lewat WA, datang langsung dilayani. Cocok buat yang waktunya mepet.","Rizky, karyawan"],
["Anak saya biasanya nangis kalau potong rambut, di sini malah minta balik lagi.","Pak Hendra, orang tua"]];
const q=document.querySelector('#slider blockquote'),c=document.querySelector('#slider cite'),dots=document.getElementById('dots');
let i=0,timer;
dots.innerHTML=T.map((_,k)=>`<button data-k="${k}" aria-label="Testimoni ${k+1}"></button>`).join('');
function show(k){i=k;q.textContent=T[k][0];c.textContent='— '+T[k][1];[...dots.children].forEach((b,n)=>b.classList.toggle('on',n==k))}
function auto(){clearInterval(timer);timer=setInterval(()=>show((i+1)%T.length),5000)}
dots.onclick=e=>{if(e.target.dataset.k){show(+e.target.dataset.k);auto()}};
show(0);auto();
