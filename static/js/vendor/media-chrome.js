/* media-chrome 4.19.3 (MIT), esbuild bundle. docs/vendor/media-chrome.md */
(()=>{var b=(t,e,i)=>()=>{if(i)throw i[0];try{return t&&(e=t(t=0)),e}catch(a){throw i=[a],a}};var Nl=(t,e)=>()=>{try{return e||t((e={exports:{}}).exports,e),e.exports}catch(i){throw e=0,i}};var h,k,Ar,ds,o,Hl,et,_u,cs,ae,$e,Gi,re,me,us,C=b(()=>{h={MEDIA_PLAY_REQUEST:"mediaplayrequest",MEDIA_PAUSE_REQUEST:"mediapauserequest",MEDIA_MUTE_REQUEST:"mediamuterequest",MEDIA_UNMUTE_REQUEST:"mediaunmuterequest",MEDIA_LOOP_REQUEST:"medialooprequest",MEDIA_VOLUME_REQUEST:"mediavolumerequest",MEDIA_SEEK_REQUEST:"mediaseekrequest",MEDIA_AIRPLAY_REQUEST:"mediaairplayrequest",MEDIA_ENTER_FULLSCREEN_REQUEST:"mediaenterfullscreenrequest",MEDIA_EXIT_FULLSCREEN_REQUEST:"mediaexitfullscreenrequest",MEDIA_PREVIEW_REQUEST:"mediapreviewrequest",MEDIA_ENTER_PIP_REQUEST:"mediaenterpiprequest",MEDIA_EXIT_PIP_REQUEST:"mediaexitpiprequest",MEDIA_ENTER_CAST_REQUEST:"mediaentercastrequest",MEDIA_EXIT_CAST_REQUEST:"mediaexitcastrequest",MEDIA_SHOW_TEXT_TRACKS_REQUEST:"mediashowtexttracksrequest",MEDIA_HIDE_TEXT_TRACKS_REQUEST:"mediahidetexttracksrequest",MEDIA_SHOW_SUBTITLES_REQUEST:"mediashowsubtitlesrequest",MEDIA_DISABLE_SUBTITLES_REQUEST:"mediadisablesubtitlesrequest",MEDIA_TOGGLE_SUBTITLES_REQUEST:"mediatogglesubtitlesrequest",MEDIA_PLAYBACK_RATE_REQUEST:"mediaplaybackraterequest",MEDIA_RENDITION_REQUEST:"mediarenditionrequest",MEDIA_AUDIO_TRACK_REQUEST:"mediaaudiotrackrequest",MEDIA_SEEK_TO_LIVE_REQUEST:"mediaseektoliverequest",REGISTER_MEDIA_STATE_RECEIVER:"registermediastatereceiver",UNREGISTER_MEDIA_STATE_RECEIVER:"unregistermediastatereceiver"},k={MEDIA_CHROME_ATTRIBUTES:"mediachromeattributes",MEDIA_CONTROLLER:"mediacontroller"},Ar={MEDIA_AIRPLAY_UNAVAILABLE:"mediaAirplayUnavailable",MEDIA_AUDIO_TRACK_ENABLED:"mediaAudioTrackEnabled",MEDIA_AUDIO_TRACK_LIST:"mediaAudioTrackList",MEDIA_AUDIO_TRACK_UNAVAILABLE:"mediaAudioTrackUnavailable",MEDIA_BUFFERED:"mediaBuffered",MEDIA_CAST_UNAVAILABLE:"mediaCastUnavailable",MEDIA_CHAPTERS_CUES:"mediaChaptersCues",MEDIA_CURRENT_TIME:"mediaCurrentTime",MEDIA_DURATION:"mediaDuration",MEDIA_ENDED:"mediaEnded",MEDIA_ERROR:"mediaError",MEDIA_ERROR_CODE:"mediaErrorCode",MEDIA_ERROR_MESSAGE:"mediaErrorMessage",MEDIA_FULLSCREEN_UNAVAILABLE:"mediaFullscreenUnavailable",MEDIA_HAS_PLAYED:"mediaHasPlayed",MEDIA_HEIGHT:"mediaHeight",MEDIA_IS_AIRPLAYING:"mediaIsAirplaying",MEDIA_IS_CASTING:"mediaIsCasting",MEDIA_IS_FULLSCREEN:"mediaIsFullscreen",MEDIA_IS_PIP:"mediaIsPip",MEDIA_LOADING:"mediaLoading",MEDIA_MUTED:"mediaMuted",MEDIA_LOOP:"mediaLoop",MEDIA_PAUSED:"mediaPaused",MEDIA_PIP_UNAVAILABLE:"mediaPipUnavailable",MEDIA_PLAYBACK_RATE:"mediaPlaybackRate",MEDIA_PREVIEW_CHAPTER:"mediaPreviewChapter",MEDIA_PREVIEW_COORDS:"mediaPreviewCoords",MEDIA_PREVIEW_IMAGE:"mediaPreviewImage",MEDIA_PREVIEW_TIME:"mediaPreviewTime",MEDIA_RENDITION_LIST:"mediaRenditionList",MEDIA_RENDITION_SELECTED:"mediaRenditionSelected",MEDIA_RENDITION_UNAVAILABLE:"mediaRenditionUnavailable",MEDIA_SEEKABLE:"mediaSeekable",MEDIA_STREAM_TYPE:"mediaStreamType",MEDIA_SUBTITLES_LIST:"mediaSubtitlesList",MEDIA_SUBTITLES_SHOWING:"mediaSubtitlesShowing",MEDIA_TARGET_LIVE_WINDOW:"mediaTargetLiveWindow",MEDIA_TIME_IS_LIVE:"mediaTimeIsLive",MEDIA_VOLUME:"mediaVolume",MEDIA_VOLUME_LEVEL:"mediaVolumeLevel",MEDIA_VOLUME_UNAVAILABLE:"mediaVolumeUnavailable",MEDIA_LANG:"mediaLang",MEDIA_WIDTH:"mediaWidth"},ds=Object.entries(Ar),o=ds.reduce((t,[e,i])=>(t[e]=i.toLowerCase(),t),{}),Hl={USER_INACTIVE_CHANGE:"userinactivechange",BREAKPOINTS_CHANGE:"breakpointchange",BREAKPOINTS_COMPUTED:"breakpointscomputed"},et=ds.reduce((t,[e,i])=>(t[e]=i.toLowerCase(),t),{...Hl}),_u=Object.entries(et).reduce((t,[e,i])=>{let a=o[e];return a&&(t[i]=a),t},{userinactivechange:"userinactive"}),cs=Object.entries(o).reduce((t,[e,i])=>{let a=et[e];return a&&(t[i]=a),t},{userinactive:"userinactivechange"}),ae={SUBTITLES:"subtitles",CAPTIONS:"captions",DESCRIPTIONS:"descriptions",CHAPTERS:"chapters",METADATA:"metadata"},$e={DISABLED:"disabled",HIDDEN:"hidden",SHOWING:"showing"},Gi={MOUSE:"mouse",PEN:"pen",TOUCH:"touch"},re={UNAVAILABLE:"unavailable",UNSUPPORTED:"unsupported"},me={LIVE:"live",ON_DEMAND:"on-demand",UNKNOWN:"unknown"},us={INLINE:"inline",FULLSCREEN:"fullscreen",PICTURE_IN_PICTURE:"picture-in-picture"}});function hs(t){return t?.map(Bl).join(" ")}function Bl(t){if(t){let{id:e,width:i,height:a}=t;return[e,i,a].filter(r=>r!=null).join(":")}}function ms(t){return t?.map($l).join(" ")}function $l(t){if(t){let{id:e,kind:i,language:a,label:r}=t;return[e,i,a,r].filter(s=>s!=null).join(":")}}function vt(t){return typeof t=="number"&&!Number.isNaN(t)&&Number.isFinite(t)}var qi,ft=b(()=>{qi=t=>new Promise(e=>setTimeout(e,t))});var ps,Es=b(()=>{ps={"Start airplay":"Start airplay","Stop airplay":"Stop airplay",Audio:"Audio",Captions:"Captions","Enable captions":"Enable captions","Disable captions":"Disable captions","Start casting":"Start casting","Stop casting":"Stop casting","Enter fullscreen mode":"Enter fullscreen mode","Exit fullscreen mode":"Exit fullscreen mode",Mute:"Mute",Unmute:"Unmute",Loop:"Loop","Enter picture in picture mode":"Enter picture in picture mode","Exit picture in picture mode":"Exit picture in picture mode",Play:"Play",Pause:"Pause","Playback rate":"Playback rate","Playback rate {playbackRate}":"Playback rate {playbackRate}",Quality:"Quality","Seek backward":"Seek backward","Seek forward":"Seek forward",Settings:"Settings",Auto:"Auto","audio player":"audio player","video player":"video player",volume:"volume",seek:"seek","closed captions":"closed captions","current playback rate":"current playback rate","playback time":"playback time","media loading":"media loading",settings:"settings","audio tracks":"audio tracks",quality:"quality",play:"play",pause:"pause",mute:"mute",unmute:"unmute","chapter: {chapterName}":"chapter: {chapterName}",live:"live",Off:"Off","start airplay":"start airplay","stop airplay":"stop airplay","start casting":"start casting","stop casting":"stop casting","enter fullscreen mode":"enter fullscreen mode","exit fullscreen mode":"exit fullscreen mode","enter picture in picture mode":"enter picture in picture mode","exit picture in picture mode":"exit picture in picture mode","seek to live":"seek to live","playing live":"playing live","seek back {seekOffset} seconds":"seek back {seekOffset} seconds","seek forward {seekOffset} seconds":"seek forward {seekOffset} seconds","Network Error":"Network Error","Decode Error":"Decode Error","Source Not Supported":"Source Not Supported","Encryption Error":"Encryption Error","A network error caused the media download to fail.":"A network error caused the media download to fail.","A media error caused playback to be aborted. The media could be corrupt or your browser does not support this format.":"A media error caused playback to be aborted. The media could be corrupt or your browser does not support this format.","An unsupported error occurred. The server or network failed, or your browser does not support this format.":"An unsupported error occurred. The server or network failed, or your browser does not support this format.","The media is encrypted and there are no keys to decrypt it.":"The media is encrypted and there are no keys to decrypt it.",hour:"hour",hours:"hours",minute:"minute",minutes:"minutes",second:"second",seconds:"seconds","{time} remaining":"{time} remaining","{currentTime} of {totalTime}":"{currentTime} of {totalTime}","video not loaded, unknown time.":"video not loaded, unknown time."}});var vs,ti,_t,fs,Wl,_s,m,W=b(()=>{Es();ti={en:ps},_t=((vs=globalThis.navigator)==null?void 0:vs.language)||"en",fs=t=>{_t=t},Wl=t=>{var e,i,a;let[r]=_t.split("-");return((e=ti[_t])==null?void 0:e[t])||((i=ti[r])==null?void 0:i[t])||((a=ti.en)==null?void 0:a[t])||t},_s=()=>{let[t]=_t.split("-");return ti[_t]?_t:ti[t]?t:"en"},m=(t,e={})=>Wl(t).replace(/\{(\w+)\}/g,(i,a)=>a in e?String(e[a]):`{${a}}`)});function pe(t,e){let i=!1;t<0&&(i=!0,t=0-t),t=t<0?0:t;let a=Math.floor(t%60),r=Math.floor(t/60%60),s=Math.floor(t/3600),l=Math.floor(e/60%60),d=Math.floor(e/3600);return(isNaN(t)||t===1/0)&&(s=r=a="0"),s=s>0||d>0?s+":":"",r=((s||l>=10)&&r<10?"0"+r:r)+":",a=a<10?"0"+a:a,(i?"-":"")+s+r+a}var gs,bs,tt,Mu,gt=b(()=>{ft();W();gs=[{singular:"hour",plural:"hours"},{singular:"minute",plural:"minutes"},{singular:"second",plural:"seconds"}],bs=(t,e)=>{let i=t===1?m(gs[e].singular):m(gs[e].plural);return`${t} ${i}`},tt=t=>{if(!vt(t))return"";let e=Math.abs(t),i=e!==t,a=new Date(0,0,0,0,0,e,0),s=[a.getHours(),a.getMinutes(),a.getSeconds()].map((l,d)=>l&&bs(l,d)).filter(l=>l).join(", ");return i?m("{time} remaining",{time:s}):e===0?bs(0,2):s};Mu=Object.freeze({length:0,start(t){let e=t>>>0;if(e>=this.length)throw new DOMException(`Failed to execute 'start' on 'TimeRanges': The index provided (${e}) is greater than or equal to the maximum bound (${this.length}).`);return 0},end(t){let e=t>>>0;if(e>=this.length)throw new DOMException(`Failed to execute 'end' on 'TimeRanges': The index provided (${e}) is greater than or equal to the maximum bound (${this.length}).`);return 0}})});var Yi,Qi,zi,Tr,As,ii,Ts,Is,n,Y,L=b(()=>{Yi=class{addEventListener(){}removeEventListener(){}dispatchEvent(){return!0}},Qi=class extends Yi{},zi=class extends Qi{constructor(){super(...arguments),this.role=null}},Tr=class{observe(){}unobserve(){}disconnect(){}},As={createElement:function(){return new ii.HTMLElement},createElementNS:function(){return new ii.HTMLElement},addEventListener(){},removeEventListener(){},dispatchEvent(t){return!1}},ii={ResizeObserver:Tr,document:As,Node:Qi,Element:zi,HTMLElement:class extends zi{constructor(){super(...arguments),this.innerHTML=""}get content(){return new ii.DocumentFragment}},DocumentFragment:class extends Yi{},customElements:{get:function(){},define:function(){},whenDefined:function(){}},localStorage:{getItem(t){return null},setItem(t,e){},removeItem(t){}},CustomEvent:function(){},getComputedStyle:function(){},navigator:{languages:[],get userAgent(){return""}},matchMedia(t){return{matches:!1,media:t}},DOMParser:class{parseFromString(e,i){return{body:{textContent:e}}}}},Ts="global"in globalThis&&globalThis?.global===globalThis||typeof window>"u"||typeof window.customElements>"u",Is=Object.keys(ii).every(t=>t in globalThis),n=Ts&&!Is?ii:globalThis,Y=Ts&&!Is?As:globalThis.document});function Zi(t,e){Ir(t).add(e),Ms.observe(t)}function Xi(t,e){let i=Ir(t);i.delete(e),i.size||Ms.unobserve(t)}var Ss,Ir,Ms,Sr=b(()=>{L();Ss=new WeakMap,Ir=t=>{let e=Ss.get(t);return e||Ss.set(t,e=new Set),e},Ms=new n.ResizeObserver(t=>{for(let e of t)for(let i of Ir(e.target))i(e)})});function K(t){let e={};for(let i of t)e[i.name]=i.value;return e}function ys(t){var e;return(e=Kl(t))!=null?e:We(t,"media-controller")}function Kl(t){var e;let{MEDIA_CONTROLLER:i}=k,a=t.getAttribute(i);if(a)return(e=ql(t))==null?void 0:e.getElementById(a)}function Mr(t=document){var e;let i=t?.activeElement;return i?(e=Mr(i.shadowRoot))!=null?e:i:null}function ql(t){var e;let i=(e=t?.getRootNode)==null?void 0:e.call(t);return i instanceof ShadowRoot||i instanceof Document?i:null}function ea(t,{depth:e=3,checkOpacity:i=!0,checkVisibilityCSS:a=!0}={}){if(t.checkVisibility)return t.checkVisibility({checkOpacity:i,checkVisibilityCSS:a});let r=t;for(;r&&e>0;){let s=getComputedStyle(r);if(i&&s.opacity==="0"||a&&s.visibility==="hidden"||s.display==="none")return!1;r=r.parentElement,e--}return!0}function ks(t,e,i,a){let r=a.x-i.x,s=a.y-i.y,l=r*r+s*s;if(l===0)return 0;let d=((t-i.x)*r+(e-i.y)*s)/l;return Math.max(0,Math.min(1,d))}function F(t,e){let i=Yl(t,a=>a===e);return i||yr(t,e)}function Yl(t,e){var i,a;let r;for(r of(i=t.querySelectorAll("style:not([media])"))!=null?i:[]){let s;try{s=(a=r.sheet)==null?void 0:a.cssRules}catch{continue}for(let l of s??[])if(e(l.selectorText))return l}}function yr(t,e){var i,a;let r=(i=t.querySelectorAll("style:not([media])"))!=null?i:[],s=r?.[r.length-1];if(!s?.sheet)return console.warn("Media Chrome: No style sheet found on style tag of",t),{style:{setProperty:()=>{},removeProperty:()=>"",getPropertyValue:()=>""}};let l=s?.sheet.insertRule(`${e}{}`,s.sheet.cssRules.length);return(a=s.sheet.cssRules)==null?void 0:a[l]}function x(t,e,i=Number.NaN){let a=t.getAttribute(e);return a!=null?+a:i}function H(t,e,i){let a=+i;if(i==null||Number.isNaN(a)){t.hasAttribute(e)&&t.removeAttribute(e);return}x(t,e,void 0)!==a&&t.setAttribute(e,`${a}`)}function _(t,e){return t.hasAttribute(e)}function g(t,e,i){if(i==null){t.hasAttribute(e)&&t.removeAttribute(e);return}_(t,e)!=i&&t.toggleAttribute(e,i)}function D(t,e,i=null){var a;return(a=t.getAttribute(e))!=null?a:i}function R(t,e,i){if(i==null){t.hasAttribute(e)&&t.removeAttribute(e);return}let a=`${i}`;D(t,e,void 0)!==a&&t.setAttribute(e,a)}var Ji,Gl,ji,Te,We,U=b(()=>{C();Ji=(t,e,i=".value")=>{let a=t.querySelector(i);a&&(a.textContent=e)},Gl=(t,e)=>{let i=`slot[name="${e}"]`,a=t.shadowRoot.querySelector(i);return a?a.children:[]},ji=(t,e)=>Gl(t,e)[0],Te=(t,e)=>!t||!e?!1:t?.contains(e)?!0:Te(t,e.getRootNode().host),We=(t,e)=>{if(!t)return null;let i=t.closest(e);return i||We(t.getRootNode().host,e)}});function zl(t){return`
    <style>
      :host {
        display: var(--media-control-display, var(--media-gesture-receiver-display, inline-block));
        box-sizing: border-box;
      }
    </style>
  `}function Zl(t){var e;let i=t.getAttribute(k.MEDIA_CONTROLLER);return i?(e=t.getRootNode())==null?void 0:e.getElementById(i):We(t,"media-controller")}var Ls,Ee,Ql,ta,j,bt,ia,aa=b(()=>{C();U();L();Ls=(t,e,i)=>{if(!e.has(t))throw TypeError("Cannot "+i)},Ee=(t,e,i)=>(Ls(t,e,"read from private field"),i?i.call(t):e.get(t)),Ql=(t,e,i)=>{if(e.has(t))throw TypeError("Cannot add the same private member more than once");e instanceof WeakSet?e.add(t):e.set(t,i)},ta=(t,e,i,a)=>(Ls(t,e,"write to private field"),a?a.call(t,i):e.set(t,i),i);bt=class extends n.HTMLElement{constructor(){if(super(),Ql(this,j,void 0),!this.shadowRoot){this.attachShadow(this.constructor.shadowRootOptions);let e=K(this.attributes);this.shadowRoot.innerHTML=this.constructor.getTemplateHTML(e)}}static get observedAttributes(){return[k.MEDIA_CONTROLLER,o.MEDIA_PAUSED]}attributeChangedCallback(e,i,a){var r,s,l,d,c;e===k.MEDIA_CONTROLLER&&(i&&((s=(r=Ee(this,j))==null?void 0:r.unassociateElement)==null||s.call(r,this),ta(this,j,null)),a&&this.isConnected&&(ta(this,j,(l=this.getRootNode())==null?void 0:l.getElementById(a)),(c=(d=Ee(this,j))==null?void 0:d.associateElement)==null||c.call(d,this)))}connectedCallback(){var e,i;this.tabIndex=-1,this.setAttribute("aria-hidden","true"),ta(this,j,Zl(this)),this.getAttribute(k.MEDIA_CONTROLLER)&&((i=(e=Ee(this,j))==null?void 0:e.associateElement)==null||i.call(e,this)),Ee(this,j)&&(Ee(this,j).addEventListener("pointerdown",this),Ee(this,j).addEventListener("click",this),Ee(this,j).hasAttribute("tabindex")||(Ee(this,j).tabIndex=0))}disconnectedCallback(){var e,i,a,r;this.getAttribute(k.MEDIA_CONTROLLER)&&((i=(e=Ee(this,j))==null?void 0:e.unassociateElement)==null||i.call(e,this)),(a=Ee(this,j))==null||a.removeEventListener("pointerdown",this),(r=Ee(this,j))==null||r.removeEventListener("click",this),ta(this,j,null)}handleEvent(e){var i;let a=(i=e.composedPath())==null?void 0:i[0];if(["video","media-controller"].includes(a?.localName)){if(e.type==="pointerdown")this._pointerType=e.pointerType;else if(e.type==="click"){let{clientX:s,clientY:l}=e,{left:d,top:c,width:y,height:M}=this.getBoundingClientRect(),I=s-d,f=l-c;if(I<0||f<0||I>y||f>M||y===0&&M===0)return;let p=this._pointerType||"mouse";if(this._pointerType=void 0,p===Gi.TOUCH){this.handleTap(e);return}else if(p===Gi.MOUSE||p===Gi.PEN){this.handleMouseClick(e);return}}}}get mediaPaused(){return _(this,o.MEDIA_PAUSED)}set mediaPaused(e){g(this,o.MEDIA_PAUSED,e)}handleTap(e){}handleMouseClick(e){let i=this.mediaPaused?h.MEDIA_PLAY_REQUEST:h.MEDIA_PAUSE_REQUEST;this.dispatchEvent(new n.CustomEvent(i,{composed:!0,bubbles:!0}))}};j=new WeakMap;bt.shadowRootOptions={mode:"open"};bt.getTemplateHTML=zl;n.customElements.get("media-gesture-receiver")||n.customElements.define("media-gesture-receiver",bt);ia=bt});function Xl(t){return`
    <style>
      
      :host([${o.MEDIA_IS_FULLSCREEN}]) ::slotted([slot=media]) {
        outline: none;
      }

      :host {
        box-sizing: border-box;
        position: relative;
        display: inline-block;
        line-height: 0;
        background-color: var(--media-background-color, #000);
        overflow: hidden;
      }

      :host(:not([${A.AUDIO}])) [part~=layer]:not([part~=media-layer]) {
        position: absolute;
        top: 0;
        left: 0;
        bottom: 0;
        right: 0;
        display: flex;
        flex-flow: column nowrap;
        align-items: start;
        pointer-events: none;
        background: none;
      }

      slot[name=media] {
        display: var(--media-slot-display, contents);
      }

      
      :host([${A.AUDIO}]) slot[name=media] {
        display: var(--media-slot-display, none);
      }

      
      :host([${A.AUDIO}]) [part~=layer][part~=gesture-layer] {
        height: 0;
        display: block;
      }

      
      :host(:not([${A.AUDIO}])[${A.GESTURES_DISABLED}]) ::slotted([slot=gestures-chrome]),
          :host(:not([${A.AUDIO}])[${A.GESTURES_DISABLED}]) media-gesture-receiver[slot=gestures-chrome] {
        display: none;
      }

      
      ::slotted(:not([slot=media]):not([slot=poster]):not(media-loading-indicator):not([role=dialog]):not([hidden])) {
        pointer-events: auto;
      }

      :host(:not([${A.AUDIO}])) *[part~=layer][part~=centered-layer] {
        align-items: center;
        justify-content: center;
      }

      :host(:not([${A.AUDIO}])) ::slotted(media-gesture-receiver[slot=gestures-chrome]),
      :host(:not([${A.AUDIO}])) media-gesture-receiver[slot=gestures-chrome] {
        align-self: stretch;
        flex-grow: 1;
      }

      slot[name=middle-chrome] {
        display: inline;
        flex-grow: 1;
        pointer-events: none;
        background: none;
      }

      
      ::slotted([slot=media]),
      ::slotted([slot=poster]) {
        width: 100%;
        height: 100%;
      }

      
      :host(:not([${A.AUDIO}])) .spacer {
        flex-grow: 1;
      }

      
      :host(:-webkit-full-screen) {
        
        width: 100% !important;
        height: 100% !important;
      }

      
      ::slotted(:not([slot=media]):not([slot=poster]):not([${A.NO_AUTOHIDE}]):not([hidden]):not([role=dialog])) {
        opacity: 1;
        transition: var(--media-control-transition-in, opacity 0.25s);
      }

      
      :host([${A.USER_INACTIVE}]:not([${o.MEDIA_PAUSED}]):not([${o.MEDIA_IS_AIRPLAYING}]):not([${o.MEDIA_IS_CASTING}]):not([${A.AUDIO}])) ::slotted(:not([slot=media]):not([slot=poster]):not([${A.NO_AUTOHIDE}]):not([role=dialog])) {
        opacity: 0;
        transition: var(--media-control-transition-out, opacity 1s);
      }

      :host([${A.USER_INACTIVE}]:not([${A.NO_AUTOHIDE}]):not([${o.MEDIA_PAUSED}]):not([${o.MEDIA_IS_CASTING}]):not([${A.AUDIO}])) ::slotted([slot=media]) {
        cursor: none;
      }

      :host([${A.USER_INACTIVE}][${A.AUTOHIDE_OVER_CONTROLS}]:not([${A.NO_AUTOHIDE}]):not([${o.MEDIA_PAUSED}]):not([${o.MEDIA_IS_CASTING}]):not([${A.AUDIO}])) * {
        --media-cursor: none;
        cursor: none;
      }


      ::slotted(media-control-bar)  {
        align-self: stretch;
      }

      
      :host(:not([${A.AUDIO}])[${o.MEDIA_HAS_PLAYED}]) slot[name=poster] {
        display: none;
      }

      ::slotted([role=dialog]) {
        width: 100%;
        height: 100%;
        align-self: center;
      }

      ::slotted([role=menu]) {
        align-self: end;
      }
    </style>

    <slot name="media" part="layer media-layer"></slot>
    <slot name="poster" part="layer poster-layer"></slot>
    <slot name="gestures-chrome" part="layer gesture-layer">
      <media-gesture-receiver slot="gestures-chrome">
        <template shadowrootmode="${ia.shadowRootOptions.mode}">
          ${ia.getTemplateHTML({})}
        </template>
      </media-gesture-receiver>
    </slot>
    <span part="layer vertical-layer">
      <slot name="top-chrome" part="top chrome"></slot>
      <slot name="middle-chrome" part="middle chrome"></slot>
      <slot name="centered-chrome" part="layer centered-layer center centered chrome"></slot>
      
      <slot part="bottom chrome"></slot>
    </span>
    <slot name="dialog" part="layer dialog-layer"></slot>
  `}function ed(t){Ds(t.target,t.contentRect.width)}function Ds(t,e){var i;if(!t.isConnected)return;let a=(i=t.getAttribute(A.BREAKPOINTS))!=null?i:jl,r=td(a),s=id(r,e),l=!1;if(Object.keys(r).forEach(d=>{if(s.includes(d)){t.hasAttribute(`breakpoint${d}`)||(t.setAttribute(`breakpoint${d}`,""),l=!0);return}t.hasAttribute(`breakpoint${d}`)&&(t.removeAttribute(`breakpoint${d}`),l=!0)}),l){let d=new CustomEvent(et.BREAKPOINTS_CHANGE,{detail:s});t.dispatchEvent(d)}t.breakpointsComputed||(t.breakpointsComputed=!0,t.dispatchEvent(new CustomEvent(et.BREAKPOINTS_COMPUTED,{bubbles:!0,composed:!0})))}function td(t){let e=t.split(/\s+/);return Object.fromEntries(e.map(i=>i.split(":")))}function id(t,e){return Object.keys(t).filter(i=>e>=parseInt(t[i]))}var Rr,G,ie,ve,fe,ai,sa,At,St,It,kr,Tt,ra,Lr,ws,wr,Rs,ri,na,la,Dr,Mt,oi,Ve,oa,A,Jl,jl,it,Cr=b(()=>{L();C();Sr();aa();W();U();aa();Rr=(t,e,i)=>{if(!e.has(t))throw TypeError("Cannot "+i)},G=(t,e,i)=>(Rr(t,e,"read from private field"),i?i.call(t):e.get(t)),ie=(t,e,i)=>{if(e.has(t))throw TypeError("Cannot add the same private member more than once");e instanceof WeakSet?e.add(t):e.set(t,i)},ve=(t,e,i,a)=>(Rr(t,e,"write to private field"),a?a.call(t,i):e.set(t,i),i),fe=(t,e,i)=>(Rr(t,e,"access private method"),i),A={AUDIO:"audio",AUTOHIDE:"autohide",BREAKPOINTS:"breakpoints",GESTURES_DISABLED:"gesturesdisabled",KEYBOARD_CONTROL:"keyboardcontrol",NO_AUTOHIDE:"noautohide",USER_INACTIVE:"userinactive",AUTOHIDE_OVER_CONTROLS:"autohideovercontrols"};Jl=Object.values(o),jl="sm:384 md:576 lg:768 xl:960";it=class extends n.HTMLElement{constructor(){if(super(),ie(this,Lr),ie(this,wr),ie(this,ri),ie(this,la),ie(this,Mt),ie(this,ai,void 0),ie(this,sa,0),ie(this,At,null),ie(this,St,null),ie(this,It,void 0),this.breakpointsComputed=!1,ie(this,kr,e=>{let i=this.media;for(let a of e){if(a.type!=="childList")continue;let r=a.removedNodes;for(let s of r){if(s.slot!="media"||a.target!=this)continue;let l=a.previousSibling&&a.previousSibling.previousElementSibling;if(!l||!i)this.mediaUnsetCallback(s);else{let d=l.slot!=="media";for(;(l=l.previousSibling)!==null;)l.slot=="media"&&(d=!1);d&&this.mediaUnsetCallback(s)}}if(i)for(let s of a.addedNodes)s===i&&this.handleMediaUpdated(i)}}),ie(this,Tt,!1),ie(this,ra,e=>{G(this,Tt)||(setTimeout(()=>{ed(e),ve(this,Tt,!1)},0),ve(this,Tt,!0))}),ie(this,Ve,void 0),ie(this,oa,()=>{if(!G(this,Ve).assignedElements({flatten:!0}).length){G(this,At)&&this.mediaUnsetCallback(G(this,At));return}this.handleMediaUpdated(this.media)}),!this.shadowRoot){this.attachShadow(this.constructor.shadowRootOptions);let e=K(this.attributes),i=this.constructor.getTemplateHTML(e);this.shadowRoot.setHTMLUnsafe?this.shadowRoot.setHTMLUnsafe(i):this.shadowRoot.innerHTML=i}ve(this,ai,new MutationObserver(G(this,kr)))}static get observedAttributes(){return[A.AUTOHIDE,A.GESTURES_DISABLED].concat(Jl).filter(e=>![o.MEDIA_RENDITION_LIST,o.MEDIA_AUDIO_TRACK_LIST,o.MEDIA_CHAPTERS_CUES,o.MEDIA_WIDTH,o.MEDIA_HEIGHT,o.MEDIA_ERROR,o.MEDIA_ERROR_MESSAGE].includes(e))}attributeChangedCallback(e,i,a){e.toLowerCase()==A.AUTOHIDE&&(this.autohide=a)}get media(){let e=this.querySelector(":scope > [slot=media]");return e?.nodeName=="SLOT"&&(e=e.assignedElements({flatten:!0})[0]),e}async handleMediaUpdated(e){e&&(ve(this,At,e),e.localName.includes("-")&&await n.customElements.whenDefined(e.localName),this.mediaSetCallback(e))}connectedCallback(){var e;G(this,ai).observe(this,{childList:!0,subtree:!0}),Zi(this,G(this,ra));let a=this.getAttribute(A.AUDIO)!=null?m("audio player"):m("video player");this.setAttribute("role","region"),this.setAttribute("aria-label",a),this.handleMediaUpdated(this.media),this.setAttribute(A.USER_INACTIVE,""),Ds(this,this.getBoundingClientRect().width);let r=this.querySelector(":scope > slot[slot=media]");r&&(ve(this,Ve,r),G(this,Ve).addEventListener("slotchange",G(this,oa))),this.addEventListener("pointerdown",this),this.addEventListener("pointermove",this),this.addEventListener("pointerup",this),this.addEventListener("mouseleave",this),this.addEventListener("keyup",this),(e=n.window)==null||e.addEventListener("mouseup",this)}disconnectedCallback(){var e;Xi(this,G(this,ra)),clearTimeout(G(this,St)),G(this,ai).disconnect(),this.media&&this.mediaUnsetCallback(this.media),(e=n.window)==null||e.removeEventListener("mouseup",this),this.removeEventListener("pointerdown",this),this.removeEventListener("pointermove",this),this.removeEventListener("pointerup",this),this.removeEventListener("mouseleave",this),this.removeEventListener("keyup",this),G(this,Ve)&&(G(this,Ve).removeEventListener("slotchange",G(this,oa)),ve(this,Ve,null)),ve(this,Tt,!1)}mediaSetCallback(e){}mediaUnsetCallback(e){ve(this,At,null)}handleEvent(e){switch(e.type){case"pointerdown":ve(this,sa,e.timeStamp);break;case"pointermove":fe(this,Lr,ws).call(this,e);break;case"pointerup":fe(this,wr,Rs).call(this,e);break;case"mouseleave":fe(this,ri,na).call(this);break;case"mouseup":this.removeAttribute(A.KEYBOARD_CONTROL);break;case"keyup":fe(this,Mt,oi).call(this),this.setAttribute(A.KEYBOARD_CONTROL,"");break}}set autohide(e){let i=Number(e);ve(this,It,isNaN(i)?0:i)}get autohide(){return(G(this,It)===void 0?2:G(this,It)).toString()}get breakpoints(){return D(this,A.BREAKPOINTS)}set breakpoints(e){R(this,A.BREAKPOINTS,e)}get audio(){return _(this,A.AUDIO)}set audio(e){g(this,A.AUDIO,e)}get gesturesDisabled(){return _(this,A.GESTURES_DISABLED)}set gesturesDisabled(e){g(this,A.GESTURES_DISABLED,e)}get keyboardControl(){return _(this,A.KEYBOARD_CONTROL)}set keyboardControl(e){g(this,A.KEYBOARD_CONTROL,e)}get noAutohide(){return _(this,A.NO_AUTOHIDE)}set noAutohide(e){g(this,A.NO_AUTOHIDE,e)}get autohideOverControls(){return _(this,A.AUTOHIDE_OVER_CONTROLS)}set autohideOverControls(e){g(this,A.AUTOHIDE_OVER_CONTROLS,e)}get userInteractive(){return _(this,A.USER_INACTIVE)}set userInteractive(e){g(this,A.USER_INACTIVE,e)}};ai=new WeakMap;sa=new WeakMap;At=new WeakMap;St=new WeakMap;It=new WeakMap;kr=new WeakMap;Tt=new WeakMap;ra=new WeakMap;Lr=new WeakSet;ws=function(t){if(t.pointerType!=="mouse"&&t.timeStamp-G(this,sa)<250)return;fe(this,la,Dr).call(this),clearTimeout(G(this,St));let e=this.hasAttribute(A.AUTOHIDE_OVER_CONTROLS);([this,this.media].includes(t.target)||e)&&fe(this,Mt,oi).call(this)};wr=new WeakSet;Rs=function(t){if(t.pointerType==="touch"){let e=!this.hasAttribute(A.USER_INACTIVE);[this,this.media].includes(t.target)&&e?fe(this,ri,na).call(this):fe(this,Mt,oi).call(this)}else t.composedPath().some(e=>["media-play-button","media-fullscreen-button"].includes(e?.localName))&&fe(this,Mt,oi).call(this)};ri=new WeakSet;na=function(){if(G(this,It)<0||this.hasAttribute(A.USER_INACTIVE))return;this.setAttribute(A.USER_INACTIVE,"");let t=new n.CustomEvent(et.USER_INACTIVE_CHANGE,{composed:!0,bubbles:!0,detail:!0});this.dispatchEvent(t)};la=new WeakSet;Dr=function(){if(!this.hasAttribute(A.USER_INACTIVE))return;this.removeAttribute(A.USER_INACTIVE);let t=new n.CustomEvent(et.USER_INACTIVE_CHANGE,{composed:!0,bubbles:!0,detail:!1});this.dispatchEvent(t)};Mt=new WeakSet;oi=function(){fe(this,la,Dr).call(this),clearTimeout(G(this,St));let t=parseInt(this.autohide);t<0||ve(this,St,setTimeout(()=>{fe(this,ri,na).call(this)},t*1e3))};Ve=new WeakMap;oa=new WeakMap;it.shadowRootOptions={mode:"open"};it.getTemplateHTML=Xl;n.customElements.get("media-container")||n.customElements.define("media-container",it)});var Cs,X,si,da,yt,kt,ca,at,He,Ke,Lt,Or=b(()=>{Cs=(t,e,i)=>{if(!e.has(t))throw TypeError("Cannot "+i)},X=(t,e,i)=>(Cs(t,e,"read from private field"),i?i.call(t):e.get(t)),si=(t,e,i)=>{if(e.has(t))throw TypeError("Cannot add the same private member more than once");e instanceof WeakSet?e.add(t):e.set(t,i)},da=(t,e,i,a)=>(Cs(t,e,"write to private field"),a?a.call(t,i):e.set(t,i),i),Lt=class{constructor(e,i,{defaultValue:a}={defaultValue:void 0}){si(this,He),si(this,yt,void 0),si(this,kt,void 0),si(this,ca,void 0),si(this,at,new Set),da(this,yt,e),da(this,kt,i),da(this,ca,new Set(a))}[Symbol.iterator](){return X(this,He,Ke).values()}get length(){return X(this,He,Ke).size}get value(){var e;return(e=[...X(this,He,Ke)].join(" "))!=null?e:""}set value(e){var i;e!==this.value&&(da(this,at,new Set),this.add(...(i=e?.split(" "))!=null?i:[]))}toString(){return this.value}item(e){return[...X(this,He,Ke)][e]}values(){return X(this,He,Ke).values()}forEach(e,i){X(this,He,Ke).forEach(e,i)}add(...e){var i,a;e.forEach(r=>X(this,at).add(r)),!(this.value===""&&!((i=X(this,yt))!=null&&i.hasAttribute(`${X(this,kt)}`)))&&((a=X(this,yt))==null||a.setAttribute(`${X(this,kt)}`,`${this.value}`))}remove(...e){var i;e.forEach(a=>X(this,at).delete(a)),(i=X(this,yt))==null||i.setAttribute(`${X(this,kt)}`,`${this.value}`)}contains(e){return X(this,He,Ke).has(e)}toggle(e,i){return typeof i<"u"?i?(this.add(e),!0):(this.remove(e),!1):this.contains(e)?(this.remove(e),!1):(this.add(e),!0)}replace(e,i){return this.remove(e),this.add(i),e===i}};yt=new WeakMap;kt=new WeakMap;ca=new WeakMap;at=new WeakMap;He=new WeakSet;Ke=function(){return X(this,at).size?X(this,at):X(this,ca)}});var ad,Os,Ur,xr,rd,ni,od,Us,rt,ot,xs,wt=b(()=>{C();ad=(t="")=>t.split(/\s+/),Os=(t="")=>{let[e,i,a]=t.split(":"),r=a?decodeURIComponent(a):void 0;return{kind:e==="cc"?ae.CAPTIONS:ae.SUBTITLES,language:i,label:r}},Ur=(t="",e={})=>ad(t).map(i=>{let a=Os(i);return{...e,...a}}),xr=t=>t?Array.isArray(t)?t.map(e=>typeof e=="string"?Os(e):e):typeof t=="string"?Ur(t):[t]:[],rd=({kind:t,label:e,language:i}={kind:"subtitles"})=>e?`${t==="captions"?"cc":"sb"}:${i}:${encodeURIComponent(e)}`:i,ni=(t=[])=>Array.prototype.map.call(t,rd).join(" "),od=(t,e)=>i=>i[t]===e,Us=t=>{let e=Object.entries(t).map(([i,a])=>od(i,a));return i=>e.every(a=>a(i))},rt=(t,e=[],i=[])=>{let a=xr(i).map(Us),r=s=>a.some(l=>l(s));Array.from(e).filter(r).forEach(s=>{s.mode=t})},ot=(t,e=()=>!0)=>{if(!t?.textTracks)return[];let i=typeof e=="function"?e:Us(e);return Array.from(t.textTracks).filter(i)},xs=t=>{var e;return!!((e=t.mediaSubtitlesShowing)!=null&&e.length)||t.hasAttribute(o.MEDIA_SUBTITLES_SHOWING)}});var Ns,Ps,Hs,li,sd,Fs,nd,Bs,Pr=b(()=>{C();U();L();Ns=t=>{var e;let{media:i,fullscreenElement:a}=t;try{let r=a&&"requestFullscreen"in a?"requestFullscreen":a&&"webkitRequestFullScreen"in a?"webkitRequestFullScreen":void 0;if(r){let s=(e=a[r])==null?void 0:e.call(a);if(s instanceof Promise)return s.catch(()=>{})}else i?.webkitEnterFullscreen?i.webkitEnterFullscreen():i?.requestFullscreen&&i.requestFullscreen()}catch(r){console.error(r)}},Ps="exitFullscreen"in Y?"exitFullscreen":"webkitExitFullscreen"in Y?"webkitExitFullscreen":"webkitCancelFullScreen"in Y?"webkitCancelFullScreen":void 0,Hs=t=>{var e;let{documentElement:i}=t;if(Ps){let a=(e=i?.[Ps])==null?void 0:e.call(i);if(a instanceof Promise)return a.catch(()=>{})}},li="fullscreenElement"in Y?"fullscreenElement":"webkitFullscreenElement"in Y?"webkitFullscreenElement":void 0,sd=t=>{let{documentElement:e,media:i}=t,a=e?.[li];return!a&&"webkitDisplayingFullscreen"in i&&"webkitPresentationMode"in i&&i.webkitDisplayingFullscreen&&i.webkitPresentationMode===us.FULLSCREEN?i:a},Fs=t=>{var e;let{media:i,documentElement:a,fullscreenElement:r=i}=t;if(!i||!a)return!1;let s=sd(t);if(!s)return!1;if(s===r||s===i)return!0;if(s.localName.includes("-")){let l=s.shadowRoot;if(!(li in l))return Te(s,r);for(;l?.[li];){if(l[li]===r)return!0;l=(e=l[li])==null?void 0:e.shadowRoot}}return!1},nd="fullscreenEnabled"in Y?"fullscreenEnabled":"webkitFullscreenEnabled"in Y?"webkitFullscreenEnabled":void 0,Bs=t=>{let{documentElement:e,media:i}=t;return!!e?.[nd]||i&&"webkitSupportsFullscreen"in i}});var ua,Nr,$s,ld,dd,cd,Hr,Fr,Ws,Vs,Ks,Gs,qs=b(()=>{L();ft();Pr();Nr=()=>{var t,e;return ua||(ua=(e=(t=Y)==null?void 0:t.createElement)==null?void 0:e.call(t,"video"),ua)},$s=async(t=Nr())=>{if(!t)return!1;let e=t.volume;t.volume=e/2+.1;let i=new AbortController,a=await Promise.race([ld(t,i.signal),dd(t,e)]);return i.abort(),a},ld=(t,e)=>new Promise(i=>{t.addEventListener("volumechange",()=>i(!0),{signal:e})}),dd=async(t,e)=>{for(let i=0;i<10;i++){if(t.volume===e)return!1;await qi(10)}return t.volume!==e},cd=/.*Version\/.*Safari\/.*/.test(n.navigator.userAgent),Hr=(t=Nr())=>n.matchMedia("(display-mode: standalone)").matches&&cd?!1:typeof t?.requestPictureInPicture=="function",Fr=(t=Nr())=>Bs({documentElement:Y,media:t}),Ws=Fr(),Vs=Hr(),Ks=!!n.WebKitPlaybackTargetAvailabilityEvent,Gs=!!n.chrome});var Rt,Br,ha,ma,ud,pa=b(()=>{C();wt();L();Rt=t=>ot(t.media,e=>[ae.SUBTITLES,ae.CAPTIONS].includes(e.kind)).sort((e,i)=>e.kind>=i.kind?1:-1),Br=t=>ot(t.media,e=>e.mode===$e.SHOWING&&[ae.SUBTITLES,ae.CAPTIONS].includes(e.kind)),ha=(t,e)=>{let i=Rt(t),a=Br(t),r=!!a.length;if(i.length){if(e===!1||r&&e!==!0)rt($e.DISABLED,i,a);else if(e===!0||!r&&e!==!1){let s=i[0],{options:l}=t;if(!l?.noSubtitlesLangPref){let M=n.localStorage.getItem("media-chrome-pref-subtitles-lang"),I=M?[M,...n.navigator.languages]:n.navigator.languages,f=i.filter(p=>I.some(T=>p.language.toLowerCase().startsWith(T.split("-")[0]))).sort((p,T)=>{let v=I.findIndex(S=>p.language.toLowerCase().startsWith(S.split("-")[0])),w=I.findIndex(S=>T.language.toLowerCase().startsWith(S.split("-")[0]));return v-w});f[0]&&(s=f[0])}let{language:d,label:c,kind:y}=s;rt($e.DISABLED,i,a),rt($e.SHOWING,i,[{language:d,label:c,kind:y}])}}},ma=(t,e)=>t===e?!0:t==null||e==null||typeof t!=typeof e?!1:typeof t=="number"&&Number.isNaN(t)&&Number.isNaN(e)?!0:typeof t!="object"?!1:Array.isArray(t)?ud(t,e):Object.entries(t).every(([i,a])=>i in e&&ma(a,e[i])),ud=(t,e)=>{let i=Array.isArray(t),a=Array.isArray(e);return i!==a?!1:i||a?t.length!==e.length?!1:t.every((r,s)=>ma(r,e[s])):!0}});var hd,Ea,md,Ys,pd,Ed,Dt,Qs=b(()=>{L();C();U();Pr();qs();pa();wt();ft();hd=Object.values(me),md=$s().then(t=>(Ea=t,Ea)),Ys=async(...t)=>{await Promise.all(t.filter(e=>e).map(async e=>{if(!("localName"in e&&e instanceof n.HTMLElement))return;let i=e.localName;if(!i.includes("-"))return;let a=n.customElements.get(i);a&&e instanceof a||(await n.customElements.whenDefined(i),n.customElements.upgrade(e))}))},pd=new n.DOMParser,Ed=t=>t&&(pd.parseFromString(t,"text/html").body.textContent||t),Dt={mediaError:{get(t,e){let{media:i}=t;if(e?.type!=="playing")return i?.error},mediaEvents:["emptied","error","playing"]},mediaErrorCode:{get(t,e){var i;let{media:a}=t;if(e?.type!=="playing")return(i=a?.error)==null?void 0:i.code},mediaEvents:["emptied","error","playing"]},mediaErrorMessage:{get(t,e){var i,a;let{media:r}=t;if(e?.type!=="playing")return(a=(i=r?.error)==null?void 0:i.message)!=null?a:""},mediaEvents:["emptied","error","playing"]},mediaWidth:{get(t){var e;let{media:i}=t;return(e=i?.videoWidth)!=null?e:0},mediaEvents:["resize"]},mediaHeight:{get(t){var e;let{media:i}=t;return(e=i?.videoHeight)!=null?e:0},mediaEvents:["resize"]},mediaPaused:{get(t){var e;let{media:i}=t;return(e=i?.paused)!=null?e:!0},set(t,e){var i;let{media:a}=e;a&&(t?a.pause():(i=a.play())==null||i.catch(()=>{}))},mediaEvents:["play","playing","pause","emptied"]},mediaHasPlayed:{get(t,e){let{media:i}=t;return i?e?e.type==="playing":!i.paused:!1},mediaEvents:["playing","emptied"]},mediaEnded:{get(t){var e;let{media:i}=t;return(e=i?.ended)!=null?e:!1},mediaEvents:["seeked","ended","emptied"]},mediaPlaybackRate:{get(t){var e;let{media:i}=t;return(e=i?.playbackRate)!=null?e:1},set(t,e){let{media:i}=e;i&&Number.isFinite(+t)&&(i.playbackRate=+t)},mediaEvents:["ratechange","loadstart"]},mediaMuted:{get(t){var e;let{media:i}=t;return(e=i?.muted)!=null?e:!1},set(t,e){let{media:i,options:{noMutedPref:a}={}}=e;if(i){i.muted=t;try{let r=n.localStorage.getItem("media-chrome-pref-muted")!==null,s=i.hasAttribute("muted");if(a){r&&n.localStorage.removeItem("media-chrome-pref-muted");return}if(s&&!r)return;n.localStorage.setItem("media-chrome-pref-muted",t?"true":"false")}catch(r){console.debug("Error setting muted pref",r)}}},mediaEvents:["volumechange"],stateOwnersUpdateHandlers:[(t,e)=>{let{options:{noMutedPref:i}}=e,{media:a}=e;if(!(!a||a.muted||i))try{let r=n.localStorage.getItem("media-chrome-pref-muted")==="true";Dt.mediaMuted.set(r,e),t(r)}catch(r){console.debug("Error getting muted pref",r)}}]},mediaLoop:{get(t){let{media:e}=t;return e?.loop},set(t,e){let{media:i}=e;i&&(i.loop=t)},mediaEvents:["medialooprequest"]},mediaVolume:{get(t){var e;let{media:i}=t;return(e=i?.volume)!=null?e:1},set(t,e){let{media:i,options:{noVolumePref:a}={}}=e;if(i){try{t==null?n.localStorage.removeItem("media-chrome-pref-volume"):!i.hasAttribute("muted")&&!a&&n.localStorage.setItem("media-chrome-pref-volume",t.toString())}catch(r){console.debug("Error setting volume pref",r)}Number.isFinite(+t)&&(i.volume=+t)}},mediaEvents:["volumechange"],stateOwnersUpdateHandlers:[(t,e)=>{let{options:{noVolumePref:i}}=e;if(!i)try{let{media:a}=e;if(!a)return;let r=n.localStorage.getItem("media-chrome-pref-volume");if(r==null)return;Dt.mediaVolume.set(+r,e),t(+r)}catch(a){console.debug("Error getting volume pref",a)}}]},mediaVolumeLevel:{get(t){let{media:e}=t;return typeof e?.volume>"u"?"high":e.muted||e.volume===0?"off":e.volume<.5?"low":e.volume<.75?"medium":"high"},mediaEvents:["volumechange"]},mediaCurrentTime:{get(t){var e;let{media:i}=t;return(e=i?.currentTime)!=null?e:0},set(t,e){let{media:i}=e;!i||!vt(t)||(i.currentTime=t)},mediaEvents:["timeupdate","loadedmetadata","seeking"]},mediaDuration:{get(t){let{media:e,options:{defaultDuration:i}={}}=t;return i&&(!e||!e.duration||Number.isNaN(e.duration)||!Number.isFinite(e.duration))?i:Number.isFinite(e?.duration)?e.duration:Number.NaN},mediaEvents:["durationchange","loadedmetadata","emptied"]},mediaLoading:{get(t){let{media:e}=t;return e?.readyState<3},mediaEvents:["waiting","playing","emptied"]},mediaSeekable:{get(t){var e;let{media:i}=t;if(!((e=i?.seekable)!=null&&e.length))return;let a=i.seekable.start(0),r=i.seekable.end(i.seekable.length-1);if(!(!a&&!r))return[Number(a.toFixed(3)),Number(r.toFixed(3))]},mediaEvents:["loadedmetadata","emptied","progress","seekablechange"]},mediaBuffered:{get(t){var e;let{media:i}=t,a=(e=i?.buffered)!=null?e:[];return Array.from(a).map((r,s)=>[Number(a.start(s).toFixed(3)),Number(a.end(s).toFixed(3))])},mediaEvents:["progress","emptied"]},mediaStreamType:{get(t){let{media:e,options:{defaultStreamType:i}={}}=t,a=[me.LIVE,me.ON_DEMAND].includes(i)?i:void 0;if(!e)return a;let{streamType:r}=e;if(hd.includes(r))return r===me.UNKNOWN?a:r;let s=e.duration;return s===1/0?me.LIVE:Number.isFinite(s)?me.ON_DEMAND:a},mediaEvents:["emptied","durationchange","loadedmetadata","streamtypechange"]},mediaTargetLiveWindow:{get(t){let{media:e}=t;if(!e)return Number.NaN;let{targetLiveWindow:i}=e,a=Dt.mediaStreamType.get(t);return(i==null||Number.isNaN(i))&&a===me.LIVE?0:i},mediaEvents:["emptied","durationchange","loadedmetadata","streamtypechange","targetlivewindowchange"]},mediaTimeIsLive:{get(t){let{media:e,options:{liveEdgeOffset:i=10}={}}=t;if(!e)return!1;if(typeof e.liveEdgeStart=="number")return Number.isNaN(e.liveEdgeStart)?!1:e.currentTime>=e.liveEdgeStart;if(!(Dt.mediaStreamType.get(t)===me.LIVE))return!1;let r=e.seekable;if(!r)return!0;if(!r.length)return!1;let s=r.end(r.length-1)-i;return e.currentTime>=s},mediaEvents:["playing","timeupdate","progress","waiting","emptied"]},mediaSubtitlesList:{get(t){return Rt(t).map(({kind:e,label:i,language:a})=>({kind:e,label:i,language:a}))},mediaEvents:["loadstart"],textTracksEvents:["addtrack","removetrack"]},mediaSubtitlesShowing:{get(t){return Br(t).map(({kind:e,label:i,language:a})=>({kind:e,label:i,language:a}))},mediaEvents:["loadstart"],textTracksEvents:["addtrack","removetrack","change"],stateOwnersUpdateHandlers:[(t,e)=>{var i,a;let{media:r,options:s}=e;if(!r)return;let l=d=>{var c;!s.defaultSubtitles||d&&![ae.CAPTIONS,ae.SUBTITLES].includes((c=d?.track)==null?void 0:c.kind)||ha(e,!0)};return r.addEventListener("loadstart",l),(i=r.textTracks)==null||i.addEventListener("addtrack",l),(a=r.textTracks)==null||a.addEventListener("removetrack",l),()=>{var d,c;r.removeEventListener("loadstart",l),(d=r.textTracks)==null||d.removeEventListener("addtrack",l),(c=r.textTracks)==null||c.removeEventListener("removetrack",l)}}]},mediaChaptersCues:{get(t){var e;let{media:i}=t;if(!i)return[];let[a]=ot(i,{kind:ae.CHAPTERS});return Array.from((e=a?.cues)!=null?e:[]).map(({text:r,startTime:s,endTime:l})=>({text:Ed(r),startTime:s,endTime:l}))},mediaEvents:["loadstart","loadedmetadata"],textTracksEvents:["addtrack","removetrack","change"],stateOwnersUpdateHandlers:[(t,e)=>{var i;let{media:a}=e;if(!a)return;let r=a.querySelector('track[kind="chapters"][default][src]'),s=(i=a.shadowRoot)==null?void 0:i.querySelector(':is(video,audio) > track[kind="chapters"][default][src]');return r?.addEventListener("load",t),s?.addEventListener("load",t),()=>{r?.removeEventListener("load",t),s?.removeEventListener("load",t)}}]},mediaIsPip:{get(t){var e,i;let{media:a,documentElement:r}=t;if(!a||!r||!r.pictureInPictureElement)return!1;if(r.pictureInPictureElement===a)return!0;if(r.pictureInPictureElement instanceof HTMLMediaElement)return(e=a.localName)!=null&&e.includes("-")?Te(a,r.pictureInPictureElement):!1;if(r.pictureInPictureElement.localName.includes("-")){let s=r.pictureInPictureElement.shadowRoot;for(;s?.pictureInPictureElement;){if(s.pictureInPictureElement===a)return!0;s=(i=s.pictureInPictureElement)==null?void 0:i.shadowRoot}}return!1},set(t,e){let{media:i}=e;if(i)if(t){if(!Y.pictureInPictureEnabled){console.warn("MediaChrome: Picture-in-picture is not enabled");return}if(!i.requestPictureInPicture){console.warn("MediaChrome: The current media does not support picture-in-picture");return}let a=()=>{console.warn("MediaChrome: The media is not ready for picture-in-picture. It must have a readyState > 0.")};i.requestPictureInPicture().catch(r=>{if(r.code===11){if(!i.src){console.warn("MediaChrome: The media is not ready for picture-in-picture. It must have a src set.");return}if(i.readyState===0&&i.preload==="none"){let s=()=>{i.removeEventListener("loadedmetadata",l),i.preload="none"},l=()=>{i.requestPictureInPicture().catch(a),s()};i.addEventListener("loadedmetadata",l),i.preload="metadata",setTimeout(()=>{i.readyState===0&&a(),s()},1e3)}else throw r}else throw r})}else Y.pictureInPictureElement&&Y.exitPictureInPicture()},mediaEvents:["enterpictureinpicture","leavepictureinpicture"]},mediaRenditionList:{get(t){var e;let{media:i}=t;return[...(e=i?.videoRenditions)!=null?e:[]].map(a=>({...a}))},mediaEvents:["emptied","loadstart"],videoRenditionsEvents:["addrendition","removerendition"]},mediaRenditionSelected:{get(t){var e,i,a;let{media:r}=t;return(a=(i=r?.videoRenditions)==null?void 0:i[(e=r.videoRenditions)==null?void 0:e.selectedIndex])==null?void 0:a.id},set(t,e){let{media:i}=e;if(!i?.videoRenditions){console.warn("MediaController: Rendition selection not supported by this media.");return}let a=t,r=Array.prototype.findIndex.call(i.videoRenditions,s=>s.id==a);i.videoRenditions.selectedIndex!=r&&(i.videoRenditions.selectedIndex=r)},mediaEvents:["emptied"],videoRenditionsEvents:["addrendition","removerendition","change"]},mediaAudioTrackList:{get(t){var e;let{media:i}=t;return[...(e=i?.audioTracks)!=null?e:[]]},mediaEvents:["emptied","loadstart"],audioTracksEvents:["addtrack","removetrack"]},mediaAudioTrackEnabled:{get(t){var e,i;let{media:a}=t;return(i=[...(e=a?.audioTracks)!=null?e:[]].find(r=>r.enabled))==null?void 0:i.id},set(t,e){let{media:i}=e;if(!i?.audioTracks){console.warn("MediaChrome: Audio track selection not supported by this media.");return}let a=t;for(let r of i.audioTracks)r.enabled=a==r.id},mediaEvents:["emptied"],audioTracksEvents:["addtrack","removetrack","change"]},mediaIsFullscreen:{get(t){return Fs(t)},set(t,e,i){var a,r;t?(Ns(e),i.detail&&!((a=e.media)!=null&&a.inert)&&((r=e.media)==null||r.focus())):Hs(e)},rootEvents:["fullscreenchange","webkitfullscreenchange"],mediaEvents:["webkitbeginfullscreen","webkitendfullscreen","webkitpresentationmodechanged"]},mediaIsCasting:{get(t){var e;let{media:i}=t;return!i?.remote||((e=i.remote)==null?void 0:e.state)==="disconnected"?!1:i.remote.state==="connected"},set(t,e){var i,a;let{media:r}=e;if(r&&!(t&&((i=r.remote)==null?void 0:i.state)!=="disconnected")&&!(!t&&((a=r.remote)==null?void 0:a.state)!=="connected")){if(typeof r.remote.prompt!="function"){console.warn("MediaChrome: Casting is not supported in this environment");return}r.remote.prompt().catch(()=>{})}},remoteEvents:["connect","connecting","disconnect"]},mediaIsAirplaying:{get(){return!1},set(t,e){let{media:i}=e;if(i){if(!(i.webkitShowPlaybackTargetPicker&&n.WebKitPlaybackTargetAvailabilityEvent)){console.error("MediaChrome: received a request to select AirPlay but AirPlay is not supported in this environment");return}i.webkitShowPlaybackTargetPicker()}},mediaEvents:["webkitcurrentplaybacktargetiswirelesschanged"]},mediaFullscreenUnavailable:{get(t){let{media:e}=t;if(!Ws||!Fr(e))return re.UNSUPPORTED}},mediaPipUnavailable:{get(t){let{media:e}=t;if(!Vs||!Hr(e))return re.UNSUPPORTED;if(e?.disablePictureInPicture)return re.UNAVAILABLE}},mediaVolumeUnavailable:{get(t){let{media:e}=t;if(Ea===!1||e?.volume==null)return re.UNSUPPORTED},stateOwnersUpdateHandlers:[t=>{Ea==null&&md.then(e=>t(e?void 0:re.UNSUPPORTED))}]},mediaCastUnavailable:{get(t,{availability:e="not-available"}={}){var i;let{media:a}=t;if(!Gs||!((i=a?.remote)!=null&&i.state))return re.UNSUPPORTED;if(!(e==null||e==="available"))return re.UNAVAILABLE},stateOwnersUpdateHandlers:[(t,e)=>{var i;let{media:a}=e;return a?(a.disableRemotePlayback||a.hasAttribute("disableremoteplayback")||(i=a?.remote)==null||i.watchAvailability(s=>{t({availability:s?"available":"not-available"})}).catch(s=>{s.name==="NotSupportedError"?t({availability:null}):t({availability:"not-available"})}),()=>{var s;(s=a?.remote)==null||s.cancelWatchAvailability().catch(()=>{})}):void 0}]},mediaAirplayUnavailable:{get(t,e){if(!Ks)return re.UNSUPPORTED;if(e?.availability==="not-available")return re.UNAVAILABLE},mediaEvents:["webkitplaybacktargetavailabilitychanged"],stateOwnersUpdateHandlers:[(t,e)=>{var i;let{media:a}=e;return a?(a.disableRemotePlayback||a.hasAttribute("disableremoteplayback")||(i=a?.remote)==null||i.watchAvailability(s=>{t({availability:s?"available":"not-available"})}).catch(s=>{s.name==="NotSupportedError"?t({availability:null}):t({availability:"not-available"})}),()=>{var s;(s=a?.remote)==null||s.cancelWatchAvailability().catch(()=>{})}):void 0}]},mediaRenditionUnavailable:{get(t){var e;let{media:i}=t;if(!i?.videoRenditions)return re.UNSUPPORTED;if(!((e=i.videoRenditions)!=null&&e.length))return re.UNAVAILABLE},mediaEvents:["emptied","loadstart"],videoRenditionsEvents:["addrendition","removerendition"]},mediaAudioTrackUnavailable:{get(t){var e,i;let{media:a}=t;if(!a?.audioTracks)return re.UNSUPPORTED;if(((i=(e=a.audioTracks)==null?void 0:e.length)!=null?i:0)<=1)return re.UNAVAILABLE},mediaEvents:["emptied","loadstart"],audioTracksEvents:["addtrack","removetrack"]},mediaLang:{get(t){let{options:{mediaLang:e}={}}=t;return e??"en"}}}});var zs,Zs=b(()=>{L();C();wt();pa();zs={[h.MEDIA_PREVIEW_REQUEST](t,e,{detail:i}){var a,r,s;let{media:l}=e,d=i??void 0,c,y;if(l&&d!=null){let[p]=ot(l,{kind:ae.METADATA,label:"thumbnails"}),T=Array.prototype.find.call((a=p?.cues)!=null?a:[],(v,w,S)=>w===0?v.endTime>d:w===S.length-1?v.startTime<=d:v.startTime<=d&&v.endTime>d);if(T){let v=/'^(?:[a-z]+:)?\/\//i.test(T.text)||(r=l?.querySelector('track[label="thumbnails"]'))==null?void 0:r.src,w=new URL(T.text,v);y=new URLSearchParams(w.hash).get("#xywh").split(",").map(te=>+te),c=w.href}}let M=t.mediaDuration.get(e),f=(s=t.mediaChaptersCues.get(e).find((p,T,v)=>T===v.length-1&&M===p.endTime?p.startTime<=d&&p.endTime>=d:p.startTime<=d&&p.endTime>d))==null?void 0:s.text;return i!=null&&f==null&&(f=""),{mediaPreviewTime:d,mediaPreviewImage:c,mediaPreviewCoords:y,mediaPreviewChapter:f}},[h.MEDIA_PAUSE_REQUEST](t,e){t["mediaPaused"].set(!0,e)},[h.MEDIA_PLAY_REQUEST](t,e){var i,a,r,s;let l="mediaPaused",c=t.mediaStreamType.get(e)===me.LIVE,y=!((i=e.options)!=null&&i.noAutoSeekToLive),M=t.mediaTargetLiveWindow.get(e)>0;if(c&&y&&!M){let I=(a=t.mediaSeekable.get(e))==null?void 0:a[1];if(I){let f=(s=(r=e.options)==null?void 0:r.seekToLiveOffset)!=null?s:0,p=I-f;t.mediaCurrentTime.set(p,e)}}t[l].set(!1,e)},[h.MEDIA_PLAYBACK_RATE_REQUEST](t,e,{detail:i}){let a="mediaPlaybackRate",r=i;t[a].set(r,e)},[h.MEDIA_MUTE_REQUEST](t,e){t["mediaMuted"].set(!0,e)},[h.MEDIA_UNMUTE_REQUEST](t,e){let i="mediaMuted";t.mediaVolume.get(e)||t.mediaVolume.set(.25,e),t[i].set(!1,e)},[h.MEDIA_LOOP_REQUEST](t,e,{detail:i}){let a="mediaLoop",r=!!i;return t[a].set(r,e),{mediaLoop:r}},[h.MEDIA_VOLUME_REQUEST](t,e,{detail:i}){let a="mediaVolume",r=i;r&&t.mediaMuted.get(e)&&t.mediaMuted.set(!1,e),t[a].set(r,e)},[h.MEDIA_SEEK_REQUEST](t,e,{detail:i}){let a="mediaCurrentTime",r=i;t[a].set(r,e)},[h.MEDIA_SEEK_TO_LIVE_REQUEST](t,e){var i,a,r;let s="mediaCurrentTime",l=(i=t.mediaSeekable.get(e))==null?void 0:i[1];if(Number.isNaN(Number(l)))return;let d=(r=(a=e.options)==null?void 0:a.seekToLiveOffset)!=null?r:0,c=l-d;t[s].set(c,e)},[h.MEDIA_SHOW_SUBTITLES_REQUEST](t,e,{detail:i}){var a;let{options:r}=e,s=Rt(e),l=xr(i),d=(a=l[0])==null?void 0:a.language;d&&!r.noSubtitlesLangPref&&n.localStorage.setItem("media-chrome-pref-subtitles-lang",d),rt($e.SHOWING,s,l)},[h.MEDIA_DISABLE_SUBTITLES_REQUEST](t,e,{detail:i}){let a=Rt(e),r=i??[];rt($e.DISABLED,a,r)},[h.MEDIA_TOGGLE_SUBTITLES_REQUEST](t,e,{detail:i}){ha(e,i)},[h.MEDIA_RENDITION_REQUEST](t,e,{detail:i}){let a="mediaRenditionSelected",r=i;t[a].set(r,e)},[h.MEDIA_AUDIO_TRACK_REQUEST](t,e,{detail:i}){let a="mediaAudioTrackEnabled",r=i;t[a].set(r,e)},[h.MEDIA_ENTER_PIP_REQUEST](t,e){let i="mediaIsPip";t.mediaIsFullscreen.get(e)&&t.mediaIsFullscreen.set(!1,e),t[i].set(!0,e)},[h.MEDIA_EXIT_PIP_REQUEST](t,e){t["mediaIsPip"].set(!1,e)},[h.MEDIA_ENTER_FULLSCREEN_REQUEST](t,e,i){let a="mediaIsFullscreen";t.mediaIsPip.get(e)&&t.mediaIsPip.set(!1,e),t[a].set(!0,e,i)},[h.MEDIA_EXIT_FULLSCREEN_REQUEST](t,e){t["mediaIsFullscreen"].set(!1,e)},[h.MEDIA_ENTER_CAST_REQUEST](t,e){let i="mediaIsCasting";t.mediaIsFullscreen.get(e)&&t.mediaIsFullscreen.set(!1,e),t[i].set(!0,e)},[h.MEDIA_EXIT_CAST_REQUEST](t,e){t["mediaIsCasting"].set(!1,e)},[h.MEDIA_AIRPLAY_REQUEST](t,e){t["mediaIsAirplaying"].set(!0,e)}}});var Xs,Js=b(()=>{Qs();pa();Zs();Xs=({media:t,fullscreenElement:e,documentElement:i,stateMediator:a=Dt,requestMap:r=zs,options:s={},monitorStateOwnersOnlyWithSubscriptions:l=!0})=>{let d=[],c={options:{...s}},y=Object.freeze({mediaPreviewTime:void 0,mediaPreviewImage:void 0,mediaPreviewCoords:void 0,mediaPreviewChapter:void 0}),M=v=>{v!=null&&(ma(v,y)||(y=Object.freeze({...y,...v}),d.forEach(w=>w(y))))},I=()=>{let v=Object.entries(a).reduce((w,[S,{get:te}])=>(w[S]=te(c),w),{});M(v)},f={},p,T=async(v,w)=>{var S,te,Xt,Jt,mt,Pe,Ne,jt,je,No,Ho,Fo,Bo,$o,Wo,Vo;let wl=!!p;if(p={...c,...p??{},...v},wl)return;await Ys(...Object.values(v));let pt=d.length>0&&w===0&&l,Ko=c.media!==p.media,Go=((S=c.media)==null?void 0:S.textTracks)!==((te=p.media)==null?void 0:te.textTracks),qo=((Xt=c.media)==null?void 0:Xt.videoRenditions)!==((Jt=p.media)==null?void 0:Jt.videoRenditions),Yo=((mt=c.media)==null?void 0:mt.audioTracks)!==((Pe=p.media)==null?void 0:Pe.audioTracks),Qo=((Ne=c.media)==null?void 0:Ne.remote)!==((jt=p.media)==null?void 0:jt.remote),zo=c.documentElement!==p.documentElement,Zo=!!c.media&&(Ko||pt),Xo=!!((je=c.media)!=null&&je.textTracks)&&(Go||pt),Jo=!!((No=c.media)!=null&&No.videoRenditions)&&(qo||pt),jo=!!((Ho=c.media)!=null&&Ho.audioTracks)&&(Yo||pt),es=!!((Fo=c.media)!=null&&Fo.remote)&&(Qo||pt),ts=!!c.documentElement&&(zo||pt),br=Zo||Xo||Jo||jo||es||ts,Et=d.length===0&&w===1&&l,is=!!p.media&&(Ko||Et),as=!!((Bo=p.media)!=null&&Bo.textTracks)&&(Go||Et),rs=!!(($o=p.media)!=null&&$o.videoRenditions)&&(qo||Et),os=!!((Wo=p.media)!=null&&Wo.audioTracks)&&(Yo||Et),ss=!!((Vo=p.media)!=null&&Vo.remote)&&(Qo||Et),ns=!!p.documentElement&&(zo||Et),ls=is||as||rs||os||ss||ns;if(!(br||ls)){Object.entries(p).forEach(([N,ei])=>{c[N]=ei}),I(),p=void 0;return}Object.entries(a).forEach(([N,{get:ei,mediaEvents:Rl=[],textTracksEvents:Dl=[],videoRenditionsEvents:Cl=[],audioTracksEvents:Ol=[],remoteEvents:Ul=[],rootEvents:xl=[],stateOwnersUpdateHandlers:Pl=[]}])=>{f[N]||(f[N]={});let ne=$=>{let q=ei(c,$);M({[N]:q})},Z;Z=f[N].mediaEvents,Rl.forEach($=>{Z&&Zo&&(c.media.removeEventListener($,Z),f[N].mediaEvents=void 0),is&&(p.media.addEventListener($,ne),f[N].mediaEvents=ne)}),Z=f[N].textTracksEvents,Dl.forEach($=>{var q,he;Z&&Xo&&((q=c.media.textTracks)==null||q.removeEventListener($,Z),f[N].textTracksEvents=void 0),as&&((he=p.media.textTracks)==null||he.addEventListener($,ne),f[N].textTracksEvents=ne)}),Z=f[N].videoRenditionsEvents,Cl.forEach($=>{var q,he;Z&&Jo&&((q=c.media.videoRenditions)==null||q.removeEventListener($,Z),f[N].videoRenditionsEvents=void 0),rs&&((he=p.media.videoRenditions)==null||he.addEventListener($,ne),f[N].videoRenditionsEvents=ne)}),Z=f[N].audioTracksEvents,Ol.forEach($=>{var q,he;Z&&jo&&((q=c.media.audioTracks)==null||q.removeEventListener($,Z),f[N].audioTracksEvents=void 0),os&&((he=p.media.audioTracks)==null||he.addEventListener($,ne),f[N].audioTracksEvents=ne)}),Z=f[N].remoteEvents,Ul.forEach($=>{var q,he;Z&&es&&((q=c.media.remote)==null||q.removeEventListener($,Z),f[N].remoteEvents=void 0),ss&&((he=p.media.remote)==null||he.addEventListener($,ne),f[N].remoteEvents=ne)}),Z=f[N].rootEvents,xl.forEach($=>{Z&&ts&&(c.documentElement.removeEventListener($,Z),f[N].rootEvents=void 0),ns&&(p.documentElement.addEventListener($,ne),f[N].rootEvents=ne)});let Ki=f[N].stateOwnersUpdateHandlers;if(Ki&&br&&(Array.isArray(Ki)?Ki:[Ki]).forEach(q=>{typeof q=="function"&&q()}),ls){let $=Pl.map(q=>q(ne,p)).filter(q=>typeof q=="function");f[N].stateOwnersUpdateHandlers=$.length===1?$[0]:$}else br&&(f[N].stateOwnersUpdateHandlers=void 0)}),Object.entries(p).forEach(([N,ei])=>{c[N]=ei}),I(),p=void 0};return T({media:t,fullscreenElement:e,documentElement:i,options:s}),{dispatch(v){let{type:w,detail:S}=v;if(r[w]&&y.mediaErrorCode==null){M(r[w](a,c,v));return}w==="mediaelementchangerequest"?T({media:S}):w==="fullscreenelementchangerequest"?T({fullscreenElement:S}):w==="documentelementchangerequest"?T({documentElement:S}):w==="optionschangerequest"&&(Object.entries(S??{}).forEach(([te,Xt])=>{c.options[te]=Xt}),I())},getState(){return y},subscribe(v){return T({},d.length+1),d.push(v),v(y),()=>{let w=d.indexOf(v);w>=0&&(T({},d.length-1),d.splice(w,1))}}}}});var qr,E,de,_e,di,Fe,ci,O,Se,ui,Ie,va,hi,fa,$r,nt,_a,Wr,Vr,sn,nn,js,en,tn,vd,fd,u,Kr,_d,gd,ln,bd,Gr,an,rn,Ad,Td,st,on,Id,dn=b(()=>{Cr();L();Or();ft();wt();C();U();Js();W();qr=(t,e,i)=>{if(!e.has(t))throw TypeError("Cannot "+i)},E=(t,e,i)=>(qr(t,e,"read from private field"),i?i.call(t):e.get(t)),de=(t,e,i)=>{if(e.has(t))throw TypeError("Cannot add the same private member more than once");e instanceof WeakSet?e.add(t):e.set(t,i)},_e=(t,e,i,a)=>(qr(t,e,"write to private field"),a?a.call(t,i):e.set(t,i),i),di=(t,e,i)=>(qr(t,e,"access private method"),i),nn=["ArrowLeft","ArrowRight","ArrowUp","ArrowDown","Enter"," ","f","m","k","c","l","j",">","<","p"],js=10,en=.025,tn=.25,vd=.25,fd=2,u={DEFAULT_SUBTITLES:"defaultsubtitles",DEFAULT_STREAM_TYPE:"defaultstreamtype",DEFAULT_DURATION:"defaultduration",FULLSCREEN_ELEMENT:"fullscreenelement",HOTKEYS:"hotkeys",KEYBOARD_BACKWARD_SEEK_OFFSET:"keyboardbackwardseekoffset",KEYBOARD_FORWARD_SEEK_OFFSET:"keyboardforwardseekoffset",KEYBOARD_DOWN_VOLUME_STEP:"keyboarddownvolumestep",KEYBOARD_UP_VOLUME_STEP:"keyboardupvolumestep",KEYS_USED:"keysused",LANG:"lang",LOOP:"loop",LIVE_EDGE_OFFSET:"liveedgeoffset",NO_AUTO_SEEK_TO_LIVE:"noautoseektolive",NO_DEFAULT_STORE:"nodefaultstore",NO_HOTKEYS:"nohotkeys",NO_MUTED_PREF:"nomutedpref",NO_SUBTITLES_LANG_PREF:"nosubtitleslangpref",NO_VOLUME_PREF:"novolumepref",SEEK_TO_LIVE_OFFSET:"seektoliveoffset"},Kr=class extends it{constructor(){super(),de(this,fa),de(this,_a),de(this,Vr),this.mediaStateReceivers=[],this.associatedElementSubscriptions=new Map,de(this,Fe,new Lt(this,u.HOTKEYS)),de(this,ci,void 0),de(this,O,void 0),de(this,Se,null),de(this,ui,void 0),de(this,Ie,void 0),de(this,va,i=>{var a;(a=E(this,O))==null||a.dispatch(i)}),de(this,hi,void 0),de(this,nt,i=>{let{key:a,shiftKey:r}=i;if(!(r&&(a==="/"||a==="?")||nn.includes(a))){this.removeEventListener("keyup",E(this,nt));return}this.keyboardShortcutHandler(i)}),this.associateElement(this);let e={};_e(this,ui,i=>{Object.entries(i).forEach(([a,r])=>{if(a in e&&e[a]===r)return;this.propagateMediaState(a,r);let s=a.toLowerCase(),l=new n.CustomEvent(cs[s],{composed:!0,detail:r});this.dispatchEvent(l)}),e=i})}static get observedAttributes(){return super.observedAttributes.concat(u.NO_HOTKEYS,u.HOTKEYS,u.DEFAULT_STREAM_TYPE,u.DEFAULT_SUBTITLES,u.DEFAULT_DURATION,u.NO_MUTED_PREF,u.NO_VOLUME_PREF,u.LANG,u.LOOP,u.LIVE_EDGE_OFFSET,u.SEEK_TO_LIVE_OFFSET,u.NO_AUTO_SEEK_TO_LIVE)}get mediaStore(){return E(this,O)}set mediaStore(e){var i,a;if(E(this,O)&&((i=E(this,Ie))==null||i.call(this),_e(this,Ie,void 0)),_e(this,O,e),!E(this,O)&&!this.hasAttribute(u.NO_DEFAULT_STORE)){di(this,fa,$r).call(this);return}_e(this,Ie,(a=E(this,O))==null?void 0:a.subscribe(E(this,ui)))}get fullscreenElement(){var e;return(e=E(this,ci))!=null?e:this}set fullscreenElement(e){var i;this.hasAttribute(u.FULLSCREEN_ELEMENT)&&this.removeAttribute(u.FULLSCREEN_ELEMENT),_e(this,ci,e),(i=E(this,O))==null||i.dispatch({type:"fullscreenelementchangerequest",detail:this.fullscreenElement})}get defaultSubtitles(){return _(this,u.DEFAULT_SUBTITLES)}set defaultSubtitles(e){g(this,u.DEFAULT_SUBTITLES,e)}get defaultStreamType(){return D(this,u.DEFAULT_STREAM_TYPE)}set defaultStreamType(e){R(this,u.DEFAULT_STREAM_TYPE,e)}get defaultDuration(){return x(this,u.DEFAULT_DURATION)}set defaultDuration(e){H(this,u.DEFAULT_DURATION,e)}get noHotkeys(){return _(this,u.NO_HOTKEYS)}set noHotkeys(e){g(this,u.NO_HOTKEYS,e)}get keysUsed(){return D(this,u.KEYS_USED)}set keysUsed(e){R(this,u.KEYS_USED,e)}get liveEdgeOffset(){return x(this,u.LIVE_EDGE_OFFSET)}set liveEdgeOffset(e){H(this,u.LIVE_EDGE_OFFSET,e)}get noAutoSeekToLive(){return _(this,u.NO_AUTO_SEEK_TO_LIVE)}set noAutoSeekToLive(e){g(this,u.NO_AUTO_SEEK_TO_LIVE,e)}get noVolumePref(){return _(this,u.NO_VOLUME_PREF)}set noVolumePref(e){g(this,u.NO_VOLUME_PREF,e)}get noMutedPref(){return _(this,u.NO_MUTED_PREF)}set noMutedPref(e){g(this,u.NO_MUTED_PREF,e)}get noSubtitlesLangPref(){return _(this,u.NO_SUBTITLES_LANG_PREF)}set noSubtitlesLangPref(e){g(this,u.NO_SUBTITLES_LANG_PREF,e)}get noDefaultStore(){return _(this,u.NO_DEFAULT_STORE)}set noDefaultStore(e){g(this,u.NO_DEFAULT_STORE,e)}get resolvedLang(){return _s()}attributeChangedCallback(e,i,a){var r,s,l,d,c,y,M,I,f,p,T,v;if(super.attributeChangedCallback(e,i,a),e===u.NO_HOTKEYS)a!==i&&a===""?(this.hasAttribute(u.HOTKEYS)&&console.warn("Media Chrome: Both `hotkeys` and `nohotkeys` have been set. All hotkeys will be disabled."),this.disableHotkeys()):a!==i&&a===null&&this.enableHotkeys();else if(e===u.HOTKEYS)E(this,Fe).value=a;else if(e===u.DEFAULT_SUBTITLES&&a!==i)(r=E(this,O))==null||r.dispatch({type:"optionschangerequest",detail:{defaultSubtitles:this.hasAttribute(u.DEFAULT_SUBTITLES)}});else if(e===u.DEFAULT_STREAM_TYPE)(l=E(this,O))==null||l.dispatch({type:"optionschangerequest",detail:{defaultStreamType:(s=this.getAttribute(u.DEFAULT_STREAM_TYPE))!=null?s:void 0}});else if(e===u.LIVE_EDGE_OFFSET&&a!==i)(d=E(this,O))==null||d.dispatch({type:"optionschangerequest",detail:{liveEdgeOffset:this.hasAttribute(u.LIVE_EDGE_OFFSET)?+this.getAttribute(u.LIVE_EDGE_OFFSET):void 0,seekToLiveOffset:this.hasAttribute(u.SEEK_TO_LIVE_OFFSET)?+this.getAttribute(u.SEEK_TO_LIVE_OFFSET):this.hasAttribute(u.LIVE_EDGE_OFFSET)?+this.getAttribute(u.LIVE_EDGE_OFFSET):void 0}});else if(e===u.SEEK_TO_LIVE_OFFSET&&a!==i)(c=E(this,O))==null||c.dispatch({type:"optionschangerequest",detail:{seekToLiveOffset:this.hasAttribute(u.SEEK_TO_LIVE_OFFSET)?+this.getAttribute(u.SEEK_TO_LIVE_OFFSET):this.hasAttribute(u.LIVE_EDGE_OFFSET)?+this.getAttribute(u.LIVE_EDGE_OFFSET):void 0}});else if(e===u.NO_AUTO_SEEK_TO_LIVE)(y=E(this,O))==null||y.dispatch({type:"optionschangerequest",detail:{noAutoSeekToLive:this.hasAttribute(u.NO_AUTO_SEEK_TO_LIVE)}});else if(e===u.FULLSCREEN_ELEMENT){let w=a?(M=this.getRootNode())==null?void 0:M.getElementById(a):void 0;_e(this,ci,w),(I=E(this,O))==null||I.dispatch({type:"fullscreenelementchangerequest",detail:this.fullscreenElement})}else e===u.LANG&&a!==i?(fs(a),(f=E(this,O))==null||f.dispatch({type:"optionschangerequest",detail:{mediaLang:a}})):e===u.LOOP&&a!==i?(p=E(this,O))==null||p.dispatch({type:h.MEDIA_LOOP_REQUEST,detail:a!=null}):e===u.NO_VOLUME_PREF&&a!==i?(T=E(this,O))==null||T.dispatch({type:"optionschangerequest",detail:{noVolumePref:this.hasAttribute(u.NO_VOLUME_PREF)}}):e===u.NO_MUTED_PREF&&a!==i&&((v=E(this,O))==null||v.dispatch({type:"optionschangerequest",detail:{noMutedPref:this.hasAttribute(u.NO_MUTED_PREF)}}))}connectedCallback(){var e,i,a;this.associateElement(this),!E(this,O)&&!this.hasAttribute(u.NO_DEFAULT_STORE)&&di(this,fa,$r).call(this),(e=E(this,O))==null||e.dispatch({type:"documentelementchangerequest",detail:Y}),(i=E(this,O))==null||i.dispatch({type:"fullscreenelementchangerequest",detail:this.fullscreenElement}),super.connectedCallback(),E(this,O)&&!E(this,Ie)&&_e(this,Ie,(a=E(this,O))==null?void 0:a.subscribe(E(this,ui))),E(this,hi)!==void 0&&E(this,O)&&this.media&&setTimeout(()=>{var r,s,l;(s=(r=this.media)==null?void 0:r.textTracks)!=null&&s.length&&((l=E(this,O))==null||l.dispatch({type:h.MEDIA_TOGGLE_SUBTITLES_REQUEST,detail:E(this,hi)}))},0),this.hasAttribute(u.NO_HOTKEYS)?this.disableHotkeys():this.enableHotkeys()}disconnectedCallback(){var e,i,a,r,s,l;if((e=super.disconnectedCallback)==null||e.call(this),this.disableHotkeys(),E(this,O)){let d=E(this,O).getState();_e(this,hi,!!((i=d.mediaSubtitlesShowing)!=null&&i.length)),(a=E(this,O))==null||a.dispatch({type:"fullscreenelementchangerequest",detail:void 0}),(r=E(this,O))==null||r.dispatch({type:"documentelementchangerequest",detail:void 0}),(s=E(this,O))==null||s.dispatch({type:h.MEDIA_TOGGLE_SUBTITLES_REQUEST,detail:!1})}E(this,Ie)&&((l=E(this,Ie))==null||l.call(this),_e(this,Ie,void 0)),this.unassociateElement(this),E(this,Se)&&(E(this,Se).remove(),_e(this,Se,null))}mediaSetCallback(e){var i;super.mediaSetCallback(e),(i=E(this,O))==null||i.dispatch({type:"mediaelementchangerequest",detail:e}),e.hasAttribute("tabindex")||(e.tabIndex=-1)}mediaUnsetCallback(e){var i;super.mediaUnsetCallback(e),(i=E(this,O))==null||i.dispatch({type:"mediaelementchangerequest",detail:void 0})}propagateMediaState(e,i){on(this.mediaStateReceivers,e,i)}associateElement(e){if(!e)return;let{associatedElementSubscriptions:i}=this;if(i.has(e))return;let a=this.registerMediaStateReceiver.bind(this),r=this.unregisterMediaStateReceiver.bind(this),s=Id(e,a,r);Object.values(h).forEach(l=>{e.addEventListener(l,E(this,va))}),i.set(e,s)}unassociateElement(e){if(!e)return;let{associatedElementSubscriptions:i}=this;if(!i.has(e))return;i.get(e)(),i.delete(e),Object.values(h).forEach(r=>{e.removeEventListener(r,E(this,va))})}registerMediaStateReceiver(e){if(!e)return;let i=this.mediaStateReceivers;i.indexOf(e)>-1||(i.push(e),E(this,O)&&Object.entries(E(this,O).getState()).forEach(([r,s])=>{on([e],r,s)}))}unregisterMediaStateReceiver(e){let i=this.mediaStateReceivers,a=i.indexOf(e);a<0||i.splice(a,1)}enableHotkeys(){this.addEventListener("keydown",di(this,_a,Wr))}disableHotkeys(){this.removeEventListener("keydown",di(this,_a,Wr)),this.removeEventListener("keyup",E(this,nt))}get hotkeys(){return E(this,Fe)}set hotkeys(e){R(this,u.HOTKEYS,e)}keyboardShortcutHandler(e){var i,a,r,s,l,d,c,y,M;let I=e.target;if(((r=(a=(i=I.getAttribute(u.KEYS_USED))==null?void 0:i.split(" "))!=null?a:I?.keysUsed)!=null?r:[]).map(S=>S==="Space"?" ":S).filter(Boolean).includes(e.key))return;let p,T,v;if(!(E(this,Fe).contains(`no${e.key.toLowerCase()}`)||e.key===" "&&E(this,Fe).contains("nospace")||e.shiftKey&&(e.key==="/"||e.key==="?")&&E(this,Fe).contains("noshift+/")))switch(e.key){case" ":case"k":p=E(this,O).getState().mediaPaused?h.MEDIA_PLAY_REQUEST:h.MEDIA_PAUSE_REQUEST,this.dispatchEvent(new n.CustomEvent(p,{composed:!0,bubbles:!0}));break;case"m":p=this.mediaStore.getState().mediaVolumeLevel==="off"?h.MEDIA_UNMUTE_REQUEST:h.MEDIA_MUTE_REQUEST,this.dispatchEvent(new n.CustomEvent(p,{composed:!0,bubbles:!0}));break;case"f":p=this.mediaStore.getState().mediaIsFullscreen?h.MEDIA_EXIT_FULLSCREEN_REQUEST:h.MEDIA_ENTER_FULLSCREEN_REQUEST,this.dispatchEvent(new n.CustomEvent(p,{composed:!0,bubbles:!0}));break;case"c":this.dispatchEvent(new n.CustomEvent(h.MEDIA_TOGGLE_SUBTITLES_REQUEST,{composed:!0,bubbles:!0}));break;case"ArrowLeft":case"j":{let S=this.hasAttribute(u.KEYBOARD_BACKWARD_SEEK_OFFSET)?+this.getAttribute(u.KEYBOARD_BACKWARD_SEEK_OFFSET):js;T=Math.max(((s=this.mediaStore.getState().mediaCurrentTime)!=null?s:0)-S,0),v=new n.CustomEvent(h.MEDIA_SEEK_REQUEST,{composed:!0,bubbles:!0,detail:T}),this.dispatchEvent(v);break}case"ArrowRight":case"l":{let S=this.hasAttribute(u.KEYBOARD_FORWARD_SEEK_OFFSET)?+this.getAttribute(u.KEYBOARD_FORWARD_SEEK_OFFSET):js;T=Math.max(((l=this.mediaStore.getState().mediaCurrentTime)!=null?l:0)+S,0),v=new n.CustomEvent(h.MEDIA_SEEK_REQUEST,{composed:!0,bubbles:!0,detail:T}),this.dispatchEvent(v);break}case"ArrowUp":{let S=this.hasAttribute(u.KEYBOARD_UP_VOLUME_STEP)?+this.getAttribute(u.KEYBOARD_UP_VOLUME_STEP):en;T=Math.min(((d=this.mediaStore.getState().mediaVolume)!=null?d:1)+S,1),v=new n.CustomEvent(h.MEDIA_VOLUME_REQUEST,{composed:!0,bubbles:!0,detail:T}),this.dispatchEvent(v);break}case"ArrowDown":{let S=this.hasAttribute(u.KEYBOARD_DOWN_VOLUME_STEP)?+this.getAttribute(u.KEYBOARD_DOWN_VOLUME_STEP):en;T=Math.max(((c=this.mediaStore.getState().mediaVolume)!=null?c:1)-S,0),v=new n.CustomEvent(h.MEDIA_VOLUME_REQUEST,{composed:!0,bubbles:!0,detail:T}),this.dispatchEvent(v);break}case"<":{let S=(y=this.mediaStore.getState().mediaPlaybackRate)!=null?y:1;T=Math.max(S-tn,vd).toFixed(2),v=new n.CustomEvent(h.MEDIA_PLAYBACK_RATE_REQUEST,{composed:!0,bubbles:!0,detail:T}),this.dispatchEvent(v);break}case">":{let S=(M=this.mediaStore.getState().mediaPlaybackRate)!=null?M:1;T=Math.min(S+tn,fd).toFixed(2),v=new n.CustomEvent(h.MEDIA_PLAYBACK_RATE_REQUEST,{composed:!0,bubbles:!0,detail:T}),this.dispatchEvent(v);break}case"/":case"?":{e.shiftKey&&di(this,Vr,sn).call(this);break}case"p":{p=this.mediaStore.getState().mediaIsPip?h.MEDIA_EXIT_PIP_REQUEST:h.MEDIA_ENTER_PIP_REQUEST,v=new n.CustomEvent(p,{composed:!0,bubbles:!0}),this.dispatchEvent(v);break}default:break}}};Fe=new WeakMap;ci=new WeakMap;O=new WeakMap;Se=new WeakMap;ui=new WeakMap;Ie=new WeakMap;va=new WeakMap;hi=new WeakMap;fa=new WeakSet;$r=function(){var t;this.mediaStore=Xs({media:this.media,fullscreenElement:this.fullscreenElement,options:{defaultSubtitles:this.hasAttribute(u.DEFAULT_SUBTITLES),defaultDuration:this.hasAttribute(u.DEFAULT_DURATION)?+this.getAttribute(u.DEFAULT_DURATION):void 0,defaultStreamType:(t=this.getAttribute(u.DEFAULT_STREAM_TYPE))!=null?t:void 0,liveEdgeOffset:this.hasAttribute(u.LIVE_EDGE_OFFSET)?+this.getAttribute(u.LIVE_EDGE_OFFSET):void 0,seekToLiveOffset:this.hasAttribute(u.SEEK_TO_LIVE_OFFSET)?+this.getAttribute(u.SEEK_TO_LIVE_OFFSET):this.hasAttribute(u.LIVE_EDGE_OFFSET)?+this.getAttribute(u.LIVE_EDGE_OFFSET):void 0,noAutoSeekToLive:this.hasAttribute(u.NO_AUTO_SEEK_TO_LIVE),noVolumePref:this.hasAttribute(u.NO_VOLUME_PREF),noMutedPref:this.hasAttribute(u.NO_MUTED_PREF),noSubtitlesLangPref:this.hasAttribute(u.NO_SUBTITLES_LANG_PREF)}})};nt=new WeakMap;_a=new WeakSet;Wr=function(t){var e;let{metaKey:i,altKey:a,key:r,shiftKey:s}=t,l=s&&(r==="/"||r==="?");if(l&&((e=E(this,Se))!=null&&e.open)){this.removeEventListener("keyup",E(this,nt));return}if(i||a||!l&&!nn.includes(r)){this.removeEventListener("keyup",E(this,nt));return}let d=t.target,c=d instanceof HTMLElement&&(d.tagName.toLowerCase()==="media-volume-range"||d.tagName.toLowerCase()==="media-time-range");[" ","ArrowLeft","ArrowRight","ArrowUp","ArrowDown"].includes(r)&&!(E(this,Fe).contains(`no${r.toLowerCase()}`)||r===" "&&E(this,Fe).contains("nospace"))&&!c&&t.preventDefault(),this.addEventListener("keyup",E(this,nt),{once:!0})};Vr=new WeakSet;sn=function(){E(this,Se)||(_e(this,Se,Y.createElement("media-keyboard-shortcuts-dialog")),this.appendChild(E(this,Se))),E(this,Se).open=!0};_d=Object.values(o),gd=Object.values(Ar),ln=t=>{var e,i,a,r;let{observedAttributes:s}=t.constructor;!s&&((e=t.nodeName)!=null&&e.includes("-"))&&(n.customElements.upgrade(t),{observedAttributes:s}=t.constructor);let l=(r=(a=(i=t?.getAttribute)==null?void 0:i.call(t,k.MEDIA_CHROME_ATTRIBUTES))==null?void 0:a.split)==null?void 0:r.call(a,/\s+/);return Array.isArray(s||l)?(s||l).filter(d=>_d.includes(d)):[]},bd=t=>{var e,i;return(e=t.nodeName)!=null&&e.includes("-")&&n.customElements.get((i=t.nodeName)==null?void 0:i.toLowerCase())&&!(t instanceof n.customElements.get(t.nodeName.toLowerCase()))&&n.customElements.upgrade(t),gd.some(a=>a in t)},Gr=t=>bd(t)||!!ln(t).length,an=t=>{var e;return(e=t?.join)==null?void 0:e.call(t,":")},rn={[o.MEDIA_SUBTITLES_LIST]:ni,[o.MEDIA_SUBTITLES_SHOWING]:ni,[o.MEDIA_SEEKABLE]:an,[o.MEDIA_BUFFERED]:t=>t?.map(an).join(" "),[o.MEDIA_PREVIEW_COORDS]:t=>t?.join(" "),[o.MEDIA_RENDITION_LIST]:hs,[o.MEDIA_AUDIO_TRACK_LIST]:ms},Ad=async(t,e,i)=>{var a,r;if(t.isConnected||await qi(0),typeof i=="boolean"||i==null)return g(t,e,i);if(typeof i=="number")return H(t,e,i);if(typeof i=="string")return R(t,e,i);if(Array.isArray(i)&&!i.length)return t.removeAttribute(e);let s=(r=(a=rn[e])==null?void 0:a.call(rn,i))!=null?r:i;return t.setAttribute(e,s)},Td=t=>{var e;return!!((e=t.closest)!=null&&e.call(t,'*[slot="media"]'))},st=(t,e)=>{if(Td(t))return;let i=(r,s)=>{var l,d;Gr(r)&&s(r);let{children:c=[]}=r??{},y=(d=(l=r?.shadowRoot)==null?void 0:l.children)!=null?d:[];[...c,...y].forEach(I=>st(I,s))},a=t?.nodeName.toLowerCase();if(a.includes("-")&&!Gr(t)){n.customElements.whenDefined(a).then(()=>{i(t,e)});return}i(t,e)},on=(t,e,i)=>{t.forEach(a=>{if(e in a){a[e]=i;return}let r=ln(a),s=e.toLowerCase();r.includes(s)&&Ad(a,s,i)})},Id=(t,e,i)=>{st(t,e);let a=M=>{var I;let f=(I=M?.composedPath()[0])!=null?I:M.target;e(f)},r=M=>{var I;let f=(I=M?.composedPath()[0])!=null?I:M.target;i(f)};t.addEventListener(h.REGISTER_MEDIA_STATE_RECEIVER,a),t.addEventListener(h.UNREGISTER_MEDIA_STATE_RECEIVER,r);let s=M=>{M.forEach(I=>{let{addedNodes:f=[],removedNodes:p=[],type:T,target:v,attributeName:w}=I;T==="childList"?(Array.prototype.forEach.call(f,S=>st(S,e)),Array.prototype.forEach.call(p,S=>st(S,i))):T==="attributes"&&w===k.MEDIA_CHROME_ATTRIBUTES&&(Gr(v)?e(v):i(v))})},l=[],d=M=>{let I=M.target;I.name!=="media"&&(l.forEach(f=>st(f,i)),l=[...I.assignedElements({flatten:!0})],l.forEach(f=>st(f,e)))};t.addEventListener("slotchange",d);let c=new MutationObserver(s);return c.observe(t,{childList:!0,attributes:!0,subtree:!0}),()=>{st(t,i),t.removeEventListener("slotchange",d),c.disconnect(),t.removeEventListener(h.REGISTER_MEDIA_STATE_RECEIVER,a),t.removeEventListener(h.UNREGISTER_MEDIA_STATE_RECEIVER,r)}};n.customElements.get("media-controller")||n.customElements.define("media-controller",Kr)});function Sd(t){return`
    <style>
      :host {
        --_tooltip-background-color: var(--media-tooltip-background-color, var(--media-secondary-color, rgba(20, 20, 30, .7)));
        --_tooltip-background: var(--media-tooltip-background, var(--_tooltip-background-color));
        --_tooltip-arrow-half-width: calc(var(--media-tooltip-arrow-width, 12px) / 2);
        --_tooltip-arrow-height: var(--media-tooltip-arrow-height, 5px);
        --_tooltip-arrow-background: var(--media-tooltip-arrow-color, var(--_tooltip-background-color));
        position: relative;
        pointer-events: none;
        display: var(--media-tooltip-display, inline-flex);
        justify-content: center;
        align-items: center;
        box-sizing: border-box;
        z-index: var(--media-tooltip-z-index, 1);
        background: var(--_tooltip-background);
        color: var(--media-text-color, var(--media-primary-color, rgb(238 238 238)));
        font: var(--media-font,
          var(--media-font-weight, 400)
          var(--media-font-size, 13px) /
          var(--media-text-content-height, var(--media-control-height, 18px))
          var(--media-font-family, helvetica neue, segoe ui, roboto, arial, sans-serif));
        padding: var(--media-tooltip-padding, .35em .7em);
        border: var(--media-tooltip-border, none);
        border-radius: var(--media-tooltip-border-radius, 5px);
        filter: var(--media-tooltip-filter, drop-shadow(0 0 4px rgba(0, 0, 0, .2)));
        white-space: var(--media-tooltip-white-space, nowrap);
      }

      :host([hidden]) {
        display: none;
      }

      img, svg {
        display: inline-block;
      }

      #arrow {
        position: absolute;
        width: 0px;
        height: 0px;
        border-style: solid;
        display: var(--media-tooltip-arrow-display, block);
      }

      :host(:not([placement])),
      :host([placement="top"]) {
        position: absolute;
        bottom: calc(100% + var(--media-tooltip-distance, 12px));
        left: 50%;
        transform: translate(calc(-50% - var(--media-tooltip-offset-x, 0px)), 0);
      }
      :host(:not([placement])) #arrow,
      :host([placement="top"]) #arrow {
        top: 100%;
        left: 50%;
        border-width: var(--_tooltip-arrow-height) var(--_tooltip-arrow-half-width) 0 var(--_tooltip-arrow-half-width);
        border-color: var(--_tooltip-arrow-background) transparent transparent transparent;
        transform: translate(calc(-50% + var(--media-tooltip-offset-x, 0px)), 0);
      }

      :host([placement="right"]) {
        position: absolute;
        left: calc(100% + var(--media-tooltip-distance, 12px));
        top: 50%;
        transform: translate(0, -50%);
      }
      :host([placement="right"]) #arrow {
        top: 50%;
        right: 100%;
        border-width: var(--_tooltip-arrow-half-width) var(--_tooltip-arrow-height) var(--_tooltip-arrow-half-width) 0;
        border-color: transparent var(--_tooltip-arrow-background) transparent transparent;
        transform: translate(0, -50%);
      }

      :host([placement="bottom"]) {
        position: absolute;
        top: calc(100% + var(--media-tooltip-distance, 12px));
        left: 50%;
        transform: translate(calc(-50% - var(--media-tooltip-offset-x, 0px)), 0);
      }
      :host([placement="bottom"]) #arrow {
        bottom: 100%;
        left: 50%;
        border-width: 0 var(--_tooltip-arrow-half-width) var(--_tooltip-arrow-height) var(--_tooltip-arrow-half-width);
        border-color: transparent transparent var(--_tooltip-arrow-background) transparent;
        transform: translate(calc(-50% + var(--media-tooltip-offset-x, 0px)), 0);
      }

      :host([placement="left"]) {
        position: absolute;
        right: calc(100% + var(--media-tooltip-distance, 12px));
        top: 50%;
        transform: translate(0, -50%);
      }
      :host([placement="left"]) #arrow {
        top: 50%;
        left: 100%;
        border-width: var(--_tooltip-arrow-half-width) 0 var(--_tooltip-arrow-half-width) var(--_tooltip-arrow-height);
        border-color: transparent transparent transparent var(--_tooltip-arrow-background);
        transform: translate(0, -50%);
      }
      
      :host([placement="none"]) #arrow {
        display: none;
      }
    </style>
    <slot></slot>
    <div id="arrow"></div>
  `}var Ct,Ot,ga,Yr=b(()=>{U();L();Ct={PLACEMENT:"placement",BOUNDS:"bounds"};Ot=class extends n.HTMLElement{constructor(){if(super(),this.updateXOffset=()=>{var e;if(!ea(this,{checkOpacity:!1,checkVisibilityCSS:!1}))return;let i=this.placement;if(i==="left"||i==="right"){this.style.removeProperty("--media-tooltip-offset-x");return}let a=getComputedStyle(this),r=(e=We(this,"#"+this.bounds))!=null?e:ys(this);if(!r)return;let{x:s,width:l}=r.getBoundingClientRect(),{x:d,width:c}=this.getBoundingClientRect(),y=d+c,M=s+l,I=a.getPropertyValue("--media-tooltip-offset-x"),f=I?parseFloat(I.replace("px","")):0,p=a.getPropertyValue("--media-tooltip-container-margin"),T=p?parseFloat(p.replace("px","")):0,v=d-s+f-T,w=y-M+f+T;if(v<0){this.style.setProperty("--media-tooltip-offset-x",`${v}px`);return}if(w>0){this.style.setProperty("--media-tooltip-offset-x",`${w}px`);return}this.style.removeProperty("--media-tooltip-offset-x")},!this.shadowRoot){this.attachShadow(this.constructor.shadowRootOptions);let e=K(this.attributes);this.shadowRoot.innerHTML=this.constructor.getTemplateHTML(e)}if(this.arrowEl=this.shadowRoot.querySelector("#arrow"),Object.prototype.hasOwnProperty.call(this,"placement")){let e=this.placement;delete this.placement,this.placement=e}}static get observedAttributes(){return[Ct.PLACEMENT,Ct.BOUNDS]}get placement(){return D(this,Ct.PLACEMENT)}set placement(e){R(this,Ct.PLACEMENT,e)}get bounds(){return D(this,Ct.BOUNDS)}set bounds(e){R(this,Ct.BOUNDS,e)}};Ot.shadowRootOptions={mode:"open"};Ot.getTemplateHTML=Sd;n.customElements.get("media-tooltip")||n.customElements.define("media-tooltip",Ot);ga=Ot});function yd(t,e={}){return`
    <style>
      :host {
        position: relative;
        font: var(--media-font,
          var(--media-font-weight, bold)
          var(--media-font-size, 14px) /
          var(--media-text-content-height, var(--media-control-height, 24px))
          var(--media-font-family, helvetica neue, segoe ui, roboto, arial, sans-serif));
        color: var(--media-text-color, var(--media-primary-color, rgb(238 238 238)));
        background: var(--media-control-background, var(--media-secondary-color, rgb(20 20 30 / .7)));
        padding: var(--media-button-padding, var(--media-control-padding, 10px));
        justify-content: var(--media-button-justify-content, center);
        display: inline-flex;
        align-items: center;
        vertical-align: middle;
        box-sizing: border-box;
        transition: background .15s linear;
        pointer-events: auto;
        cursor: var(--media-cursor, pointer);
        -webkit-tap-highlight-color: transparent;
      }

      
      :host(:focus-visible) {
        box-shadow: var(--media-focus-box-shadow, inset 0 0 0 2px rgb(27 127 204 / .9));
        outline: 0;
      }
      
      :host(:where(:focus)) {
        box-shadow: none;
        outline: 0;
      }

      :host(:hover) {
        background: var(--media-control-hover-background, rgba(50 50 70 / .7));
      }

      slot[name="icon"] {
        display: inline-flex;
        align-items: center;
      }

      svg, img, ::slotted(svg), ::slotted(img) {
        width: var(--media-button-icon-width);
        height: var(--media-button-icon-height, var(--media-control-height, 24px));
        transform: var(--media-button-icon-transform);
        transition: var(--media-button-icon-transition);
        fill: var(--media-icon-color, var(--media-primary-color, rgb(238 238 238)));
        vertical-align: middle;
        max-width: 100%;
        max-height: 100%;
        min-width: 100%;
      }

      media-tooltip {
        
        max-width: 0;
        overflow-x: clip;
        opacity: 0;
        transition: opacity .3s, max-width 0s 9s;
      }

      :host(:hover) media-tooltip,
      :host(:focus-visible) media-tooltip {
        max-width: 100vw;
        opacity: 1;
        transition: opacity .3s;
      }

      :host([notooltip]) slot[name="tooltip"] {
        display: none;
      }
    </style>

    ${this.getSlotTemplateHTML(t,e)}

    <slot name="tooltip">
      <media-tooltip part="tooltip" aria-hidden="true">
        <template shadowrootmode="${ga.shadowRootOptions.mode}">
          ${ga.getTemplateHTML({})}
        </template>
        <slot name="tooltip-content">
          ${this.getTooltipContentHTML(t)}
        </slot>
      </media-tooltip>
    </slot>
  `}function kd(t,e){return`
    <slot></slot>
  `}function Ld(){return""}var zr,Q,Ut,ba,Md,Me,Pt,qe,xt,Aa,Qr,cn,Ge,P,oe=b(()=>{C();Yr();U();L();zr=(t,e,i)=>{if(!e.has(t))throw TypeError("Cannot "+i)},Q=(t,e,i)=>(zr(t,e,"read from private field"),i?i.call(t):e.get(t)),Ut=(t,e,i)=>{if(e.has(t))throw TypeError("Cannot add the same private member more than once");e instanceof WeakSet?e.add(t):e.set(t,i)},ba=(t,e,i,a)=>(zr(t,e,"write to private field"),a?a.call(t,i):e.set(t,i),i),Md=(t,e,i)=>(zr(t,e,"access private method"),i),Ge={TOOLTIP_PLACEMENT:"tooltipplacement",DISABLED:"disabled",NO_TOOLTIP:"notooltip"};P=class extends n.HTMLElement{constructor(){if(super(),Ut(this,Qr),Ut(this,Me,void 0),this.preventClick=!1,this.tooltipEl=null,Ut(this,Pt,e=>{this.preventClick||this.handleClick(e),setTimeout(Q(this,qe),0)}),Ut(this,qe,()=>{var e,i;(i=(e=this.tooltipEl)==null?void 0:e.updateXOffset)==null||i.call(e)}),Ut(this,xt,e=>{let{key:i}=e;if(!this.keysUsed.includes(i)){this.removeEventListener("keyup",Q(this,xt));return}this.preventClick||this.handleClick(e)}),Ut(this,Aa,e=>{let{metaKey:i,altKey:a,key:r}=e;if(i||a||!this.keysUsed.includes(r)){this.removeEventListener("keyup",Q(this,xt));return}this.addEventListener("keyup",Q(this,xt),{once:!0})}),!this.shadowRoot){this.attachShadow(this.constructor.shadowRootOptions);let e=K(this.attributes),i=this.constructor.getTemplateHTML(e);this.shadowRoot.setHTMLUnsafe?this.shadowRoot.setHTMLUnsafe(i):this.shadowRoot.innerHTML=i}this.tooltipEl=this.shadowRoot.querySelector("media-tooltip")}static get observedAttributes(){return["disabled",Ge.TOOLTIP_PLACEMENT,k.MEDIA_CONTROLLER,o.MEDIA_LANG]}enable(){this.addEventListener("click",Q(this,Pt)),this.addEventListener("keydown",Q(this,Aa)),this.tabIndex=0}disable(){this.removeEventListener("click",Q(this,Pt)),this.removeEventListener("keydown",Q(this,Aa)),this.removeEventListener("keyup",Q(this,xt)),this.tabIndex=-1}attributeChangedCallback(e,i,a){var r,s,l,d,c;e===k.MEDIA_CONTROLLER?(i&&((s=(r=Q(this,Me))==null?void 0:r.unassociateElement)==null||s.call(r,this),ba(this,Me,null)),a&&this.isConnected&&(ba(this,Me,(l=this.getRootNode())==null?void 0:l.getElementById(a)),(c=(d=Q(this,Me))==null?void 0:d.associateElement)==null||c.call(d,this))):e==="disabled"&&a!==i?a==null?this.enable():this.disable():e===Ge.TOOLTIP_PLACEMENT&&this.tooltipEl&&a!==i?this.tooltipEl.placement=a:e===o.MEDIA_LANG&&(this.shadowRoot.querySelector('slot[name="tooltip-content"]').innerHTML=this.constructor.getTooltipContentHTML()),Q(this,qe).call(this)}connectedCallback(){var e,i,a;let{style:r}=F(this.shadowRoot,":host");r.setProperty("display",`var(--media-control-display, var(--${this.localName}-display, inline-flex))`),this.hasAttribute("disabled")?this.disable():this.enable(),this.setAttribute("role","button");let s=this.getAttribute(k.MEDIA_CONTROLLER);s&&(ba(this,Me,(e=this.getRootNode())==null?void 0:e.getElementById(s)),(a=(i=Q(this,Me))==null?void 0:i.associateElement)==null||a.call(i,this)),n.customElements.whenDefined("media-tooltip").then(()=>Md(this,Qr,cn).call(this))}disconnectedCallback(){var e,i;this.disable(),(i=(e=Q(this,Me))==null?void 0:e.unassociateElement)==null||i.call(e,this),ba(this,Me,null),this.removeEventListener("mouseenter",Q(this,qe)),this.removeEventListener("focus",Q(this,qe)),this.removeEventListener("click",Q(this,Pt))}get keysUsed(){return["Enter"," "]}get tooltipPlacement(){return D(this,Ge.TOOLTIP_PLACEMENT)}set tooltipPlacement(e){R(this,Ge.TOOLTIP_PLACEMENT,e)}get mediaController(){return D(this,k.MEDIA_CONTROLLER)}set mediaController(e){R(this,k.MEDIA_CONTROLLER,e)}get disabled(){return _(this,Ge.DISABLED)}set disabled(e){g(this,Ge.DISABLED,e)}get noTooltip(){return _(this,Ge.NO_TOOLTIP)}set noTooltip(e){g(this,Ge.NO_TOOLTIP,e)}handleClick(e){}};Me=new WeakMap;Pt=new WeakMap;qe=new WeakMap;xt=new WeakMap;Aa=new WeakMap;Qr=new WeakSet;cn=function(){this.addEventListener("mouseenter",Q(this,qe)),this.addEventListener("focus",Q(this,qe)),this.addEventListener("click",Q(this,Pt));let t=this.tooltipPlacement;t&&this.tooltipEl&&(this.tooltipEl.placement=t)};P.shadowRootOptions={mode:"open"};P.getTemplateHTML=yd;P.getSlotTemplateHTML=kd;P.getTooltipContentHTML=Ld;n.customElements.get("media-chrome-button")||n.customElements.define("media-chrome-button",P)});function wd(t){return`
    <style>
      :host([${o.MEDIA_IS_AIRPLAYING}]) slot[name=icon] slot:not([name=exit]) {
        display: none !important;
      }

      
      :host(:not([${o.MEDIA_IS_AIRPLAYING}])) slot[name=icon] slot:not([name=enter]) {
        display: none !important;
      }

      :host([${o.MEDIA_IS_AIRPLAYING}]) slot[name=tooltip-enter],
      :host(:not([${o.MEDIA_IS_AIRPLAYING}])) slot[name=tooltip-exit] {
        display: none;
      }
    </style>

    <slot name="icon">
      <slot name="enter">${un}</slot>
      <slot name="exit">${un}</slot>
    </slot>
  `}function Rd(){return`
    <slot name="tooltip-enter">${m("start airplay")}</slot>
    <slot name="tooltip-exit">${m("stop airplay")}</slot>
  `}var un,hn,mi,mn=b(()=>{oe();L();C();W();U();un=`<svg aria-hidden="true" viewBox="0 0 26 24">
  <path d="M22.13 3H3.87a.87.87 0 0 0-.87.87v13.26a.87.87 0 0 0 .87.87h3.4L9 16H5V5h16v11h-4l1.72 2h3.4a.87.87 0 0 0 .87-.87V3.87a.87.87 0 0 0-.86-.87Zm-8.75 11.44a.5.5 0 0 0-.76 0l-4.91 5.73a.5.5 0 0 0 .38.83h9.82a.501.501 0 0 0 .38-.83l-4.91-5.73Z"/>
</svg>
`;hn=t=>{let e=t.mediaIsAirplaying?m("stop airplay"):m("start airplay");t.setAttribute("aria-label",e)},mi=class extends P{static get observedAttributes(){return[...super.observedAttributes,o.MEDIA_IS_AIRPLAYING,o.MEDIA_AIRPLAY_UNAVAILABLE]}connectedCallback(){super.connectedCallback(),hn(this)}attributeChangedCallback(e,i,a){super.attributeChangedCallback(e,i,a),e===o.MEDIA_IS_AIRPLAYING&&hn(this)}get mediaIsAirplaying(){return _(this,o.MEDIA_IS_AIRPLAYING)}set mediaIsAirplaying(e){g(this,o.MEDIA_IS_AIRPLAYING,e)}get mediaAirplayUnavailable(){return D(this,o.MEDIA_AIRPLAY_UNAVAILABLE)}set mediaAirplayUnavailable(e){R(this,o.MEDIA_AIRPLAY_UNAVAILABLE,e)}handleClick(){let e=new n.CustomEvent(h.MEDIA_AIRPLAY_REQUEST,{composed:!0,bubbles:!0});this.dispatchEvent(e)}};mi.getSlotTemplateHTML=wd;mi.getTooltipContentHTML=Rd;n.customElements.get("media-airplay-button")||n.customElements.define("media-airplay-button",mi)});function Od(t){return`
    <style>
      :host([aria-checked="true"]) slot[name=off] {
        display: none !important;
      }

      
      :host(:not([aria-checked="true"])) slot[name=on] {
        display: none !important;
      }

      :host([aria-checked="true"]) slot[name=tooltip-enable],
      :host(:not([aria-checked="true"])) slot[name=tooltip-disable] {
        display: none;
      }
    </style>

    <slot name="icon">
      <slot name="on">${Dd}</slot>
      <slot name="off">${Cd}</slot>
    </slot>
  `}function Ud(){return`
    <slot name="tooltip-enable">${m("Enable captions")}</slot>
    <slot name="tooltip-disable">${m("Disable captions")}</slot>
  `}var Dd,Cd,pn,pi,En,vn,fn=b(()=>{oe();L();C();wt();W();Dd=`<svg aria-hidden="true" viewBox="0 0 26 24">
  <path d="M22.83 5.68a2.58 2.58 0 0 0-2.3-2.5c-3.62-.24-11.44-.24-15.06 0a2.58 2.58 0 0 0-2.3 2.5c-.23 4.21-.23 8.43 0 12.64a2.58 2.58 0 0 0 2.3 2.5c3.62.24 11.44.24 15.06 0a2.58 2.58 0 0 0 2.3-2.5c.23-4.21.23-8.43 0-12.64Zm-11.39 9.45a3.07 3.07 0 0 1-1.91.57 3.06 3.06 0 0 1-2.34-1 3.75 3.75 0 0 1-.92-2.67 3.92 3.92 0 0 1 .92-2.77 3.18 3.18 0 0 1 2.43-1 2.94 2.94 0 0 1 2.13.78c.364.359.62.813.74 1.31l-1.43.35a1.49 1.49 0 0 0-1.51-1.17 1.61 1.61 0 0 0-1.29.58 2.79 2.79 0 0 0-.5 1.89 3 3 0 0 0 .49 1.93 1.61 1.61 0 0 0 1.27.58 1.48 1.48 0 0 0 1-.37 2.1 2.1 0 0 0 .59-1.14l1.4.44a3.23 3.23 0 0 1-1.07 1.69Zm7.22 0a3.07 3.07 0 0 1-1.91.57 3.06 3.06 0 0 1-2.34-1 3.75 3.75 0 0 1-.92-2.67 3.88 3.88 0 0 1 .93-2.77 3.14 3.14 0 0 1 2.42-1 3 3 0 0 1 2.16.82 2.8 2.8 0 0 1 .73 1.31l-1.43.35a1.49 1.49 0 0 0-1.51-1.21 1.61 1.61 0 0 0-1.29.58A2.79 2.79 0 0 0 15 12a3 3 0 0 0 .49 1.93 1.61 1.61 0 0 0 1.27.58 1.44 1.44 0 0 0 1-.37 2.1 2.1 0 0 0 .6-1.15l1.4.44a3.17 3.17 0 0 1-1.1 1.7Z"/>
</svg>`,Cd=`<svg aria-hidden="true" viewBox="0 0 26 24">
  <path d="M17.73 14.09a1.4 1.4 0 0 1-1 .37 1.579 1.579 0 0 1-1.27-.58A3 3 0 0 1 15 12a2.8 2.8 0 0 1 .5-1.85 1.63 1.63 0 0 1 1.29-.57 1.47 1.47 0 0 1 1.51 1.2l1.43-.34A2.89 2.89 0 0 0 19 9.07a3 3 0 0 0-2.14-.78 3.14 3.14 0 0 0-2.42 1 3.91 3.91 0 0 0-.93 2.78 3.74 3.74 0 0 0 .92 2.66 3.07 3.07 0 0 0 2.34 1 3.07 3.07 0 0 0 1.91-.57 3.17 3.17 0 0 0 1.07-1.74l-1.4-.45c-.083.43-.3.822-.62 1.12Zm-7.22 0a1.43 1.43 0 0 1-1 .37 1.58 1.58 0 0 1-1.27-.58A3 3 0 0 1 7.76 12a2.8 2.8 0 0 1 .5-1.85 1.63 1.63 0 0 1 1.29-.57 1.47 1.47 0 0 1 1.51 1.2l1.43-.34a2.81 2.81 0 0 0-.74-1.32 2.94 2.94 0 0 0-2.13-.78 3.18 3.18 0 0 0-2.43 1 4 4 0 0 0-.92 2.78 3.74 3.74 0 0 0 .92 2.66 3.07 3.07 0 0 0 2.34 1 3.07 3.07 0 0 0 1.91-.57 3.23 3.23 0 0 0 1.07-1.74l-1.4-.45a2.06 2.06 0 0 1-.6 1.07Zm12.32-8.41a2.59 2.59 0 0 0-2.3-2.51C18.72 3.05 15.86 3 13 3c-2.86 0-5.72.05-7.53.17a2.59 2.59 0 0 0-2.3 2.51c-.23 4.207-.23 8.423 0 12.63a2.57 2.57 0 0 0 2.3 2.5c1.81.13 4.67.19 7.53.19 2.86 0 5.72-.06 7.53-.19a2.57 2.57 0 0 0 2.3-2.5c.23-4.207.23-8.423 0-12.63Zm-1.49 12.53a1.11 1.11 0 0 1-.91 1.11c-1.67.11-4.45.18-7.43.18-2.98 0-5.76-.07-7.43-.18a1.11 1.11 0 0 1-.91-1.11c-.21-4.14-.21-8.29 0-12.43a1.11 1.11 0 0 1 .91-1.11C7.24 4.56 10 4.49 13 4.49s5.76.07 7.43.18a1.11 1.11 0 0 1 .91 1.11c.21 4.14.21 8.29 0 12.43Z"/>
</svg>`;pn=t=>{t.setAttribute("aria-checked",xs(t).toString())},pi=class extends P{static get observedAttributes(){return[...super.observedAttributes,o.MEDIA_SUBTITLES_LIST,o.MEDIA_SUBTITLES_SHOWING]}connectedCallback(){super.connectedCallback(),this.setAttribute("role","button"),this.setAttribute("aria-label",m("closed captions")),pn(this)}attributeChangedCallback(e,i,a){super.attributeChangedCallback(e,i,a),e===o.MEDIA_SUBTITLES_SHOWING&&pn(this)}get mediaSubtitlesList(){return En(this,o.MEDIA_SUBTITLES_LIST)}set mediaSubtitlesList(e){vn(this,o.MEDIA_SUBTITLES_LIST,e)}get mediaSubtitlesShowing(){return En(this,o.MEDIA_SUBTITLES_SHOWING)}set mediaSubtitlesShowing(e){vn(this,o.MEDIA_SUBTITLES_SHOWING,e)}handleClick(){this.dispatchEvent(new n.CustomEvent(h.MEDIA_TOGGLE_SUBTITLES_REQUEST,{composed:!0,bubbles:!0}))}};pi.getSlotTemplateHTML=Od;pi.getTooltipContentHTML=Ud;En=(t,e)=>{let i=t.getAttribute(e);return i?Ur(i):[]},vn=(t,e,i)=>{if(!i?.length){t.removeAttribute(e);return}let a=ni(i);t.getAttribute(e)!==a&&t.setAttribute(e,a)};n.customElements.get("media-captions-button")||n.customElements.define("media-captions-button",pi)});function Nd(t){return`
    <style>
      :host([${o.MEDIA_IS_CASTING}]) slot[name=icon] slot:not([name=exit]) {
        display: none !important;
      }

      
      :host(:not([${o.MEDIA_IS_CASTING}])) slot[name=icon] slot:not([name=enter]) {
        display: none !important;
      }

      :host([${o.MEDIA_IS_CASTING}]) slot[name=tooltip-enter],
      :host(:not([${o.MEDIA_IS_CASTING}])) slot[name=tooltip-exit] {
        display: none;
      }
    </style>

    <slot name="icon">
      <slot name="enter">${xd}</slot>
      <slot name="exit">${Pd}</slot>
    </slot>
  `}function Hd(){return`
    <slot name="tooltip-enter">${m("Start casting")}</slot>
    <slot name="tooltip-exit">${m("Stop casting")}</slot>
  `}var xd,Pd,_n,Ei,gn=b(()=>{oe();L();C();W();U();xd='<svg aria-hidden="true" viewBox="0 0 24 24"><g><path class="cast_caf_icon_arch0" d="M1,18 L1,21 L4,21 C4,19.3 2.66,18 1,18 L1,18 Z"/><path class="cast_caf_icon_arch1" d="M1,14 L1,16 C3.76,16 6,18.2 6,21 L8,21 C8,17.13 4.87,14 1,14 L1,14 Z"/><path class="cast_caf_icon_arch2" d="M1,10 L1,12 C5.97,12 10,16.0 10,21 L12,21 C12,14.92 7.07,10 1,10 L1,10 Z"/><path class="cast_caf_icon_box" d="M21,3 L3,3 C1.9,3 1,3.9 1,5 L1,8 L3,8 L3,5 L21,5 L21,19 L14,19 L14,21 L21,21 C22.1,21 23,20.1 23,19 L23,5 C23,3.9 22.1,3 21,3 L21,3 Z"/></g></svg>',Pd='<svg aria-hidden="true" viewBox="0 0 24 24"><g><path class="cast_caf_icon_arch0" d="M1,18 L1,21 L4,21 C4,19.3 2.66,18 1,18 L1,18 Z"/><path class="cast_caf_icon_arch1" d="M1,14 L1,16 C3.76,16 6,18.2 6,21 L8,21 C8,17.13 4.87,14 1,14 L1,14 Z"/><path class="cast_caf_icon_arch2" d="M1,10 L1,12 C5.97,12 10,16.0 10,21 L12,21 C12,14.92 7.07,10 1,10 L1,10 Z"/><path class="cast_caf_icon_box" d="M21,3 L3,3 C1.9,3 1,3.9 1,5 L1,8 L3,8 L3,5 L21,5 L21,19 L14,19 L14,21 L21,21 C22.1,21 23,20.1 23,19 L23,5 C23,3.9 22.1,3 21,3 L21,3 Z"/><path class="cast_caf_icon_boxfill" d="M5,7 L5,8.63 C8,8.6 13.37,14 13.37,17 L19,17 L19,7 Z"/></g></svg>';_n=t=>{let e=t.mediaIsCasting?m("stop casting"):m("start casting");t.setAttribute("aria-label",e)},Ei=class extends P{static get observedAttributes(){return[...super.observedAttributes,o.MEDIA_IS_CASTING,o.MEDIA_CAST_UNAVAILABLE]}connectedCallback(){super.connectedCallback(),_n(this)}attributeChangedCallback(e,i,a){super.attributeChangedCallback(e,i,a),e===o.MEDIA_IS_CASTING&&_n(this)}get mediaIsCasting(){return _(this,o.MEDIA_IS_CASTING)}set mediaIsCasting(e){g(this,o.MEDIA_IS_CASTING,e)}get mediaCastUnavailable(){return D(this,o.MEDIA_CAST_UNAVAILABLE)}set mediaCastUnavailable(e){R(this,o.MEDIA_CAST_UNAVAILABLE,e)}handleClick(){let e=this.mediaIsCasting?h.MEDIA_EXIT_CAST_REQUEST:h.MEDIA_ENTER_CAST_REQUEST;this.dispatchEvent(new n.CustomEvent(e,{composed:!0,bubbles:!0}))}};Ei.getSlotTemplateHTML=Nd;Ei.getTooltipContentHTML=Hd;n.customElements.get("media-cast-button")||n.customElements.define("media-cast-button",Ei)});function Fd(t){return`
    <style>
      :host {
        font: var(--media-font,
          var(--media-font-weight, normal)
          var(--media-font-size, 14px) /
          var(--media-text-content-height, var(--media-control-height, 24px))
          var(--media-font-family, helvetica neue, segoe ui, roboto, arial, sans-serif));
        color: var(--media-text-color, var(--media-primary-color, rgb(238 238 238)));
        display: var(--media-dialog-display, inline-flex);
        justify-content: center;
        align-items: center;
        
        transition-behavior: allow-discrete;
        visibility: hidden;
        opacity: 0;
        transform: translateY(2px) scale(.99);
        pointer-events: none;
      }

      :host([open]) {
        transition: display .2s, visibility 0s, opacity .2s ease-out, transform .15s ease-out;
        visibility: visible;
        opacity: 1;
        transform: translateY(0) scale(1);
        pointer-events: auto;
      }

      #content {
        display: flex;
        position: relative;
        box-sizing: border-box;
        width: min(320px, 100%);
        word-wrap: break-word;
        max-height: 100%;
        overflow: auto;
        text-align: center;
        line-height: 1.4;
      }
    </style>
    ${this.getSlotTemplateHTML(t)}
  `}function Bd(t){return`
    <slot id="content"></slot>
  `}var io,dt,Be,ao,lt,Ia,fi,ct,Ta,Zr,Xr,bn,Jr,An,jr,Tn,eo,In,to,Sn,vi,ye,Sa=b(()=>{L();U();io=(t,e,i)=>{if(!e.has(t))throw TypeError("Cannot "+i)},dt=(t,e,i)=>(io(t,e,"read from private field"),i?i.call(t):e.get(t)),Be=(t,e,i)=>{if(e.has(t))throw TypeError("Cannot add the same private member more than once");e instanceof WeakSet?e.add(t):e.set(t,i)},ao=(t,e,i,a)=>(io(t,e,"write to private field"),a?a.call(t,i):e.set(t,i),i),lt=(t,e,i)=>(io(t,e,"access private method"),i);vi={OPEN:"open",ANCHOR:"anchor"},ye=class extends n.HTMLElement{constructor(){super(),Be(this,Ta),Be(this,Xr),Be(this,Jr),Be(this,jr),Be(this,eo),Be(this,to),Be(this,Ia,!1),Be(this,fi,null),Be(this,ct,null)}static get observedAttributes(){return[vi.OPEN,vi.ANCHOR]}get open(){return _(this,vi.OPEN)}set open(e){g(this,vi.OPEN,e)}handleEvent(e){switch(e.type){case"invoke":lt(this,jr,Tn).call(this,e);break;case"focusout":lt(this,eo,In).call(this,e);break;case"keydown":lt(this,to,Sn).call(this,e);break}}connectedCallback(){lt(this,Ta,Zr).call(this),this.role||(this.role="dialog"),this.addEventListener("invoke",this),this.addEventListener("focusout",this),this.addEventListener("keydown",this)}disconnectedCallback(){this.removeEventListener("invoke",this),this.removeEventListener("focusout",this),this.removeEventListener("keydown",this)}attributeChangedCallback(e,i,a){lt(this,Ta,Zr).call(this),e===vi.OPEN&&a!==i&&(this.open?lt(this,Xr,bn).call(this):lt(this,Jr,An).call(this))}focus(){ao(this,fi,Mr());let e=!this.dispatchEvent(new Event("focus",{composed:!0,cancelable:!0})),i=!this.dispatchEvent(new Event("focusin",{composed:!0,bubbles:!0,cancelable:!0}));if(e||i)return;let a=this.querySelector('[autofocus], [tabindex]:not([tabindex="-1"]), [role="menu"]');a?.focus()}get keysUsed(){return["Escape","Tab"]}};Ia=new WeakMap;fi=new WeakMap;ct=new WeakMap;Ta=new WeakSet;Zr=function(){if(!dt(this,Ia)&&(ao(this,Ia,!0),!this.shadowRoot)){this.attachShadow(this.constructor.shadowRootOptions);let t=K(this.attributes);this.shadowRoot.innerHTML=this.constructor.getTemplateHTML(t),queueMicrotask(()=>{let{style:e}=F(this.shadowRoot,":host");e.setProperty("transition","display .15s, visibility .15s, opacity .15s ease-in, transform .15s ease-in")})}};Xr=new WeakSet;bn=function(){var t;(t=dt(this,ct))==null||t.setAttribute("aria-expanded","true"),this.dispatchEvent(new Event("open",{composed:!0,bubbles:!0})),this.addEventListener("transitionend",()=>this.focus(),{once:!0})};Jr=new WeakSet;An=function(){var t;(t=dt(this,ct))==null||t.setAttribute("aria-expanded","false"),this.dispatchEvent(new Event("close",{composed:!0,bubbles:!0}))};jr=new WeakSet;Tn=function(t){ao(this,ct,t.relatedTarget),Te(this,t.relatedTarget)||(this.open=!this.open)};eo=new WeakSet;In=function(t){var e;Te(this,t.relatedTarget)||((e=dt(this,fi))==null||e.focus(),dt(this,ct)&&dt(this,ct)!==t.relatedTarget&&this.open&&(this.open=!1))};to=new WeakSet;Sn=function(t){var e,i,a,r,s;let{key:l,ctrlKey:d,altKey:c,metaKey:y}=t;d||c||y||this.keysUsed.includes(l)&&(t.preventDefault(),t.stopPropagation(),l==="Tab"?(t.shiftKey?(i=(e=this.previousElementSibling)==null?void 0:e.focus)==null||i.call(e):(r=(a=this.nextElementSibling)==null?void 0:a.focus)==null||r.call(a),this.blur()):l==="Escape"&&((s=dt(this,fi))==null||s.focus(),this.open=!1))};ye.shadowRootOptions={mode:"open"};ye.getTemplateHTML=Fd;ye.getSlotTemplateHTML=Bd;n.customElements.get("media-chrome-dialog")||n.customElements.define("media-chrome-dialog",ye)});function $d(t){return`
    <style>
      :host {
        --_focus-box-shadow: var(--media-focus-box-shadow, inset 0 0 0 2px rgb(27 127 204 / .9));
        --_media-range-padding: var(--media-range-padding, var(--media-control-padding, 10px));

        box-shadow: var(--_focus-visible-box-shadow, none);
        background: var(--media-control-background, var(--media-secondary-color, rgb(20 20 30 / .7)));
        height: calc(var(--media-control-height, 24px) + 2 * var(--_media-range-padding));
        display: inline-flex;
        align-items: center;
        
        vertical-align: middle;
        box-sizing: border-box;
        position: relative;
        width: 100px;
        transition: background .15s linear;
        cursor: var(--media-cursor, pointer);
        pointer-events: auto;
        touch-action: none; 
      }

      
      input[type=range]:focus {
        outline: 0;
      }
      input[type=range]:focus::-webkit-slider-runnable-track {
        outline: 0;
      }

      :host(:hover) {
        background: var(--media-control-hover-background, rgb(50 50 70 / .7));
      }

      #leftgap {
        padding-left: var(--media-range-padding-left, var(--_media-range-padding));
      }

      #rightgap {
        padding-right: var(--media-range-padding-right, var(--_media-range-padding));
      }

      #startpoint,
      #endpoint {
        position: absolute;
      }

      #endpoint {
        right: 0;
      }

      #container {
        
        width: var(--media-range-track-width, 100%);
        transform: translate(var(--media-range-track-translate-x, 0px), var(--media-range-track-translate-y, 0px));
        position: relative;
        height: 100%;
        display: flex;
        align-items: center;
        min-width: 40px;
      }

      #range {
        
        display: var(--media-time-range-hover-display, block);
        bottom: var(--media-time-range-hover-bottom, 0);
        height: var(--media-time-range-hover-height, max(100% , 25px));
        width: 100%;
        position: absolute;
        cursor: var(--media-cursor, pointer);

        -webkit-appearance: none; 
        -webkit-tap-highlight-color: transparent;
        background: transparent; 
        margin: 0;
        z-index: 1;
      }

      @media (hover: hover) {
        #range {
          bottom: var(--media-time-range-hover-bottom, 0);
          height: var(--media-time-range-hover-height, max(100%, 20px));
        }
      }

      
      
      #range::-webkit-slider-thumb {
        -webkit-appearance: none;
        background: transparent;
        width: .1px;
        height: .1px;
      }

      
      #range::-moz-range-thumb {
        background: transparent;
        border: transparent;
        width: .1px;
        height: .1px;
      }

      #appearance {
        height: var(--media-range-track-height, 4px);
        display: flex;
        flex-direction: column;
        justify-content: center;
        width: 100%;
        position: absolute;
        
        will-change: transform;
      }

      #track {
        background: var(--media-range-track-background, rgb(255 255 255 / .2));
        border-radius: var(--media-range-track-border-radius, 1px);
        border: var(--media-range-track-border, none);
        outline: var(--media-range-track-outline);
        outline-offset: var(--media-range-track-outline-offset);
        backdrop-filter: var(--media-range-track-backdrop-filter);
        -webkit-backdrop-filter: var(--media-range-track-backdrop-filter);
        box-shadow: var(--media-range-track-box-shadow, none);
        position: absolute;
        width: 100%;
        height: 100%;
        overflow: hidden;
      }

      #progress,
      #pointer {
        position: absolute;
        height: 100%;
        will-change: width;
      }

      #progress {
        background: var(--media-range-bar-color, var(--media-primary-color, rgb(238 238 238)));
        transition: var(--media-range-track-transition);
      }

      #pointer {
        background: var(--media-range-track-pointer-background);
        border-right: var(--media-range-track-pointer-border-right);
        transition: visibility .25s, opacity .25s;
        visibility: hidden;
        opacity: 0;
      }

      @media (hover: hover) {
        :host(:hover) #pointer {
          transition: visibility .5s, opacity .5s;
          visibility: visible;
          opacity: 1;
        }
      }

      #thumb,
      ::slotted([slot=thumb]) {
        width: var(--media-range-thumb-width, 10px);
        height: var(--media-range-thumb-height, 10px);
        transition: var(--media-range-thumb-transition);
        transform: var(--media-range-thumb-transform, none);
        opacity: var(--media-range-thumb-opacity, 1);
        translate: -50%;
        position: absolute;
        left: 0;
        cursor: var(--media-cursor, pointer);
      }

      #thumb {
        border-radius: var(--media-range-thumb-border-radius, 10px);
        background: var(--media-range-thumb-background, var(--media-primary-color, rgb(238 238 238)));
        box-shadow: var(--media-range-thumb-box-shadow, 1px 1px 1px transparent);
        border: var(--media-range-thumb-border, none);
      }

      :host([disabled]) #thumb {
        background-color: #777;
      }

      .segments #appearance {
        height: var(--media-range-segment-hover-height, 7px);
      }

      #track {
        clip-path: url(#segments-clipping);
      }

      #segments {
        --segments-gap: var(--media-range-segments-gap, 2px);
        position: absolute;
        width: 100%;
        height: 100%;
      }

      #segments-clipping {
        transform: translateX(calc(var(--segments-gap) / 2));
      }

      #segments-clipping:empty {
        display: none;
      }

      #segments-clipping rect {
        height: var(--media-range-track-height, 4px);
        y: calc((var(--media-range-segment-hover-height, 7px) - var(--media-range-track-height, 4px)) / 2);
        transition: var(--media-range-segment-transition, transform .1s ease-in-out);
        transform: var(--media-range-segment-transform, scaleY(1));
        transform-origin: center;
      }

      /* Visible label for accessibility - positioned off-screen but technically visible (Firefox requires visible labels) */
      #range-label {
        position: absolute;
        left: -10000px;
        background: var(--media-control-background, var(--media-secondary-color, rgb(20 20 30 / .7)));
        pointer-events: none;
      }
    </style>
    <div id="leftgap"></div>
    <div id="container">
      <div id="startpoint"></div>
      <div id="endpoint"></div>
      <div id="appearance">
        <div id="track" part="track">
          <div id="pointer"></div>
          <div id="progress" part="progress"></div>
        </div>
        <slot name="thumb">
          <div id="thumb" part="thumb"></div>
        </slot>
        <svg id="segments" aria-hidden="true"><clipPath id="segments-clipping"></clipPath></svg>
      </div>
        <input id="range" type="range" min="0" max="1" step="any" value="0">
        <label for="range" id="range-label"></label>

      ${this.getContainerTemplateHTML(t)}
    </div>
    <div id="rightgap"></div>
  `}function Wd(t){return""}var uo,V,ee,Ye,ge,ke,Ua,Ma,ya,be,Ca,ka,La,wa,ho,Mn,Ra,ro,Da,oo,Oa,mo,so,yn,no,kn,lo,Ln,co,wn,Le,xa=b(()=>{C();L();U();Sr();uo=(t,e,i)=>{if(!e.has(t))throw TypeError("Cannot "+i)},V=(t,e,i)=>(uo(t,e,"read from private field"),i?i.call(t):e.get(t)),ee=(t,e,i)=>{if(e.has(t))throw TypeError("Cannot add the same private member more than once");e instanceof WeakSet?e.add(t):e.set(t,i)},Ye=(t,e,i,a)=>(uo(t,e,"write to private field"),a?a.call(t,i):e.set(t,i),i),ge=(t,e,i)=>(uo(t,e,"access private method"),i);Le=class extends n.HTMLElement{constructor(){if(super(),ee(this,ho),ee(this,Ra),ee(this,Da),ee(this,Oa),ee(this,so),ee(this,no),ee(this,lo),ee(this,co),ee(this,ke,void 0),ee(this,Ua,void 0),ee(this,Ma,void 0),ee(this,ya,void 0),ee(this,be,{}),ee(this,Ca,[]),ee(this,ka,()=>{if(this.range.matches(":focus-visible")){let{style:e}=F(this.shadowRoot,":host");e.setProperty("--_focus-visible-box-shadow","var(--_focus-box-shadow)")}}),ee(this,La,()=>{let{style:e}=F(this.shadowRoot,":host");e.removeProperty("--_focus-visible-box-shadow")}),ee(this,wa,()=>{let e=this.shadowRoot.querySelector("#segments-clipping");e&&e.parentNode.append(e)}),!this.shadowRoot){this.attachShadow(this.constructor.shadowRootOptions);let e=K(this.attributes),i=this.constructor.getTemplateHTML(e);this.shadowRoot.setHTMLUnsafe?this.shadowRoot.setHTMLUnsafe(i):this.shadowRoot.innerHTML=i}this.container=this.shadowRoot.querySelector("#container"),Ye(this,Ma,this.shadowRoot.querySelector("#startpoint")),Ye(this,ya,this.shadowRoot.querySelector("#endpoint")),this.range=this.shadowRoot.querySelector("#range"),this.appearance=this.shadowRoot.querySelector("#appearance")}static get observedAttributes(){return["disabled","aria-disabled",k.MEDIA_CONTROLLER]}attributeChangedCallback(e,i,a){var r,s,l,d,c;e===k.MEDIA_CONTROLLER?(i&&((s=(r=V(this,ke))==null?void 0:r.unassociateElement)==null||s.call(r,this),Ye(this,ke,null)),a&&this.isConnected&&(Ye(this,ke,(l=this.getRootNode())==null?void 0:l.getElementById(a)),(c=(d=V(this,ke))==null?void 0:d.associateElement)==null||c.call(d,this))):(e==="disabled"||e==="aria-disabled"&&i!==a)&&(a==null?(this.range.removeAttribute(e),ge(this,Ra,ro).call(this)):(this.range.setAttribute(e,a),ge(this,Da,oo).call(this)))}connectedCallback(){var e,i,a;let{style:r}=F(this.shadowRoot,":host");r.setProperty("display",`var(--media-control-display, var(--${this.localName}-display, inline-flex))`),V(this,be).pointer=F(this.shadowRoot,"#pointer"),V(this,be).progress=F(this.shadowRoot,"#progress"),V(this,be).thumb=F(this.shadowRoot,'#thumb, ::slotted([slot="thumb"])'),V(this,be).activeSegment=F(this.shadowRoot,"#segments-clipping rect:nth-child(0)");let s=this.getAttribute(k.MEDIA_CONTROLLER);s&&(Ye(this,ke,(e=this.getRootNode())==null?void 0:e.getElementById(s)),(a=(i=V(this,ke))==null?void 0:i.associateElement)==null||a.call(i,this)),this.updateBar(),this.shadowRoot.addEventListener("focusin",V(this,ka)),this.shadowRoot.addEventListener("focusout",V(this,La)),ge(this,Ra,ro).call(this),Zi(this.container,V(this,wa))}disconnectedCallback(){var e,i;ge(this,Da,oo).call(this),(i=(e=V(this,ke))==null?void 0:e.unassociateElement)==null||i.call(e,this),Ye(this,ke,null),this.shadowRoot.removeEventListener("focusin",V(this,ka)),this.shadowRoot.removeEventListener("focusout",V(this,La)),Xi(this.container,V(this,wa))}updatePointerBar(e){var i;(i=V(this,be).pointer)==null||i.style.setProperty("width",`${this.getPointerRatio(e)*100}%`)}updateBar(){var e,i;let a=this.range.valueAsNumber*100;(e=V(this,be).progress)==null||e.style.setProperty("width",`${a}%`),(i=V(this,be).thumb)==null||i.style.setProperty("left",`${a}%`)}updateSegments(e){let i=this.shadowRoot.querySelector("#segments-clipping");if(i.textContent="",this.container.classList.toggle("segments",!!e?.length),!e?.length)return;let a=[...new Set([+this.range.min,...e.flatMap(s=>[s.start,s.end]),+this.range.max])];Ye(this,Ca,[...a]);let r=a.pop();for(let[s,l]of a.entries()){let[d,c]=[s===0,s===a.length-1],y=d?"calc(var(--segments-gap) / -1)":`${l*100}%`,I=`calc(${((c?r:a[s+1])-l)*100}%${d||c?"":" - var(--segments-gap)"})`,f=Y.createElementNS("http://www.w3.org/2000/svg","rect"),p=yr(this.shadowRoot,`#segments-clipping rect:nth-child(${s+1})`);p.style.setProperty("x",y),p.style.setProperty("width",I),i.append(f)}}getPointerRatio(e){return ks(e.clientX,e.clientY,V(this,Ma).getBoundingClientRect(),V(this,ya).getBoundingClientRect())}get dragging(){return this.hasAttribute("dragging")}handleEvent(e){switch(e.type){case"pointermove":ge(this,co,wn).call(this,e);break;case"input":this.updateBar();break;case"pointerenter":ge(this,so,yn).call(this,e);break;case"pointerdown":ge(this,Oa,mo).call(this,e);break;case"pointerup":ge(this,no,kn).call(this);break;case"pointerleave":ge(this,lo,Ln).call(this);break}}get keysUsed(){return["ArrowUp","ArrowRight","ArrowDown","ArrowLeft"]}};ke=new WeakMap;Ua=new WeakMap;Ma=new WeakMap;ya=new WeakMap;be=new WeakMap;Ca=new WeakMap;ka=new WeakMap;La=new WeakMap;wa=new WeakMap;ho=new WeakSet;Mn=function(t){let e=V(this,be).activeSegment;if(!e)return;let i=this.getPointerRatio(t),r=`#segments-clipping rect:nth-child(${V(this,Ca).findIndex((s,l,d)=>{let c=d[l+1];return c!=null&&i>=s&&i<=c})+1})`;(e.selectorText!=r||!e.style.transform)&&(e.selectorText=r,e.style.setProperty("transform","var(--media-range-segment-hover-transform, scaleY(2))"))};Ra=new WeakSet;ro=function(){this.hasAttribute("disabled")||!this.isConnected||(this.addEventListener("input",this),this.addEventListener("pointerdown",this),this.addEventListener("pointerenter",this))};Da=new WeakSet;oo=function(){var t,e;this.removeEventListener("input",this),this.removeEventListener("pointerdown",this),this.removeEventListener("pointerenter",this),this.removeEventListener("pointerleave",this),(t=n.window)==null||t.removeEventListener("pointerup",this),(e=n.window)==null||e.removeEventListener("pointermove",this)};Oa=new WeakSet;mo=function(t){var e;Ye(this,Ua,t.composedPath().includes(this.range)),(e=n.window)==null||e.addEventListener("pointerup",this,{once:!0})};so=new WeakSet;yn=function(t){var e;t.pointerType!=="mouse"&&ge(this,Oa,mo).call(this,t),this.addEventListener("pointerleave",this,{once:!0}),(e=n.window)==null||e.addEventListener("pointermove",this)};no=new WeakSet;kn=function(){var t;(t=n.window)==null||t.removeEventListener("pointerup",this),this.toggleAttribute("dragging",!1),this.range.disabled=this.hasAttribute("disabled")};lo=new WeakSet;Ln=function(){var t,e;this.removeEventListener("pointerleave",this),(t=n.window)==null||t.removeEventListener("pointermove",this),this.toggleAttribute("dragging",!1),this.range.disabled=this.hasAttribute("disabled"),(e=V(this,be).activeSegment)==null||e.style.removeProperty("transform")};co=new WeakSet;wn=function(t){t.pointerType==="pen"&&t.buttons===0||(this.toggleAttribute("dragging",t.buttons===1||t.pointerType!=="mouse"),this.updatePointerBar(t),ge(this,ho,Mn).call(this,t),this.dragging&&(t.pointerType!=="mouse"||!V(this,Ua))&&(this.range.disabled=!0,this.range.valueAsNumber=this.getPointerRatio(t),this.range.dispatchEvent(new Event("input",{bubbles:!0,composed:!0}))))};Le.shadowRootOptions={mode:"open"};Le.getTemplateHTML=$d;Le.getContainerTemplateHTML=Wd;n.customElements.get("media-chrome-range")||n.customElements.define("media-chrome-range",Le)});function Kd(t){return`
    <style>
      :host {
        
        box-sizing: border-box;
        display: var(--media-control-display, var(--media-control-bar-display, inline-flex));
        color: var(--media-text-color, var(--media-primary-color, rgb(238 238 238)));
        --media-loading-indicator-icon-height: 44px;
      }

      ::slotted(media-time-range),
      ::slotted(media-volume-range) {
        min-height: 100%;
      }

      ::slotted(media-time-range),
      ::slotted(media-clip-selector) {
        flex-grow: 1;
      }

      ::slotted([role="menu"]) {
        position: absolute;
      }
    </style>

    <slot></slot>
  `}var Rn,Pa,Vd,Na,we,_i,Dn=b(()=>{C();U();L();Rn=(t,e,i)=>{if(!e.has(t))throw TypeError("Cannot "+i)},Pa=(t,e,i)=>(Rn(t,e,"read from private field"),i?i.call(t):e.get(t)),Vd=(t,e,i)=>{if(e.has(t))throw TypeError("Cannot add the same private member more than once");e instanceof WeakSet?e.add(t):e.set(t,i)},Na=(t,e,i,a)=>(Rn(t,e,"write to private field"),a?a.call(t,i):e.set(t,i),i);_i=class extends n.HTMLElement{constructor(){if(super(),Vd(this,we,void 0),!this.shadowRoot){this.attachShadow(this.constructor.shadowRootOptions);let e=K(this.attributes);this.shadowRoot.innerHTML=this.constructor.getTemplateHTML(e)}}static get observedAttributes(){return[k.MEDIA_CONTROLLER]}attributeChangedCallback(e,i,a){var r,s,l,d,c;e===k.MEDIA_CONTROLLER&&(i&&((s=(r=Pa(this,we))==null?void 0:r.unassociateElement)==null||s.call(r,this),Na(this,we,null)),a&&this.isConnected&&(Na(this,we,(l=this.getRootNode())==null?void 0:l.getElementById(a)),(c=(d=Pa(this,we))==null?void 0:d.associateElement)==null||c.call(d,this)))}connectedCallback(){var e,i,a;let r=this.getAttribute(k.MEDIA_CONTROLLER);r&&(Na(this,we,(e=this.getRootNode())==null?void 0:e.getElementById(r)),(a=(i=Pa(this,we))==null?void 0:i.associateElement)==null||a.call(i,this))}disconnectedCallback(){var e,i;(i=(e=Pa(this,we))==null?void 0:e.unassociateElement)==null||i.call(e,this),Na(this,we,null)}};we=new WeakMap;_i.shadowRootOptions={mode:"open"};_i.getTemplateHTML=Kd;n.customElements.get("media-control-bar")||n.customElements.define("media-control-bar",_i)});function qd(t,e={}){return`
    <style>
      :host {
        font: var(--media-font,
          var(--media-font-weight, normal)
          var(--media-font-size, 14px) /
          var(--media-text-content-height, var(--media-control-height, 24px))
          var(--media-font-family, helvetica neue, segoe ui, roboto, arial, sans-serif));
        color: var(--media-text-color, var(--media-primary-color, rgb(238 238 238)));
        background: var(--media-text-background, var(--media-control-background, var(--media-secondary-color, rgb(20 20 30 / .7))));
        padding: var(--media-control-padding, 10px);
        display: inline-flex;
        justify-content: center;
        align-items: center;
        vertical-align: middle;
        box-sizing: border-box;
        text-align: center;
        pointer-events: auto;
      }

      
      :host(:focus-visible) {
        box-shadow: var(--media-focus-box-shadow, inset 0 0 0 2px rgb(27 127 204 / .9));
        outline: 0;
      }

      
      :host(:where(:focus)) {
        box-shadow: none;
        outline: 0;
      }
    </style>

    ${this.getSlotTemplateHTML(t,e)}
  `}function Yd(t,e){return`
    <slot></slot>
  `}var Cn,Ha,Gd,Fa,Re,se,Nt=b(()=>{C();U();L();Cn=(t,e,i)=>{if(!e.has(t))throw TypeError("Cannot "+i)},Ha=(t,e,i)=>(Cn(t,e,"read from private field"),i?i.call(t):e.get(t)),Gd=(t,e,i)=>{if(e.has(t))throw TypeError("Cannot add the same private member more than once");e instanceof WeakSet?e.add(t):e.set(t,i)},Fa=(t,e,i,a)=>(Cn(t,e,"write to private field"),a?a.call(t,i):e.set(t,i),i);se=class extends n.HTMLElement{constructor(){if(super(),Gd(this,Re,void 0),!this.shadowRoot){this.attachShadow(this.constructor.shadowRootOptions);let e=K(this.attributes);this.shadowRoot.innerHTML=this.constructor.getTemplateHTML(e)}}static get observedAttributes(){return[k.MEDIA_CONTROLLER]}attributeChangedCallback(e,i,a){var r,s,l,d,c;e===k.MEDIA_CONTROLLER&&(i&&((s=(r=Ha(this,Re))==null?void 0:r.unassociateElement)==null||s.call(r,this),Fa(this,Re,null)),a&&this.isConnected&&(Fa(this,Re,(l=this.getRootNode())==null?void 0:l.getElementById(a)),(c=(d=Ha(this,Re))==null?void 0:d.associateElement)==null||c.call(d,this)))}connectedCallback(){var e,i,a;let{style:r}=F(this.shadowRoot,":host");r.setProperty("display",`var(--media-control-display, var(--${this.localName}-display, inline-flex))`);let s=this.getAttribute(k.MEDIA_CONTROLLER);s&&(Fa(this,Re,(e=this.getRootNode())==null?void 0:e.getElementById(s)),(a=(i=Ha(this,Re))==null?void 0:i.associateElement)==null||a.call(i,this))}disconnectedCallback(){var e,i;(i=(e=Ha(this,Re))==null?void 0:e.unassociateElement)==null||i.call(e,this),Fa(this,Re,null)}};Re=new WeakMap;se.shadowRootOptions={mode:"open"};se.getTemplateHTML=qd;se.getSlotTemplateHTML=Yd;n.customElements.get("media-text-display")||n.customElements.define("media-text-display",se)});function Zd(t,e){return`
    <slot>${pe(e.mediaDuration)}</slot>
  `}var Un,On,Qd,zd,gi,Ba,xn=b(()=>{Nt();L();gt();C();U();Un=(t,e,i)=>{if(!e.has(t))throw TypeError("Cannot "+i)},On=(t,e,i)=>(Un(t,e,"read from private field"),i?i.call(t):e.get(t)),Qd=(t,e,i)=>{if(e.has(t))throw TypeError("Cannot add the same private member more than once");e instanceof WeakSet?e.add(t):e.set(t,i)},zd=(t,e,i,a)=>(Un(t,e,"write to private field"),a?a.call(t,i):e.set(t,i),i);Ba=class extends se{constructor(){var e;super(),Qd(this,gi,void 0),zd(this,gi,this.shadowRoot.querySelector("slot")),On(this,gi).textContent=pe((e=this.mediaDuration)!=null?e:0)}static get observedAttributes(){return[...super.observedAttributes,o.MEDIA_DURATION]}attributeChangedCallback(e,i,a){e===o.MEDIA_DURATION&&(On(this,gi).textContent=pe(+a)),super.attributeChangedCallback(e,i,a)}get mediaDuration(){return x(this,o.MEDIA_DURATION)}set mediaDuration(e){H(this,o.MEDIA_DURATION,e)}};gi=new WeakMap;Ba.getSlotTemplateHTML=Zd;n.customElements.get("media-duration-display")||n.customElements.define("media-duration-display",Ba)});var Xd,Jd,$a,Pn=b(()=>{W();Xd={2:m("Network Error"),3:m("Decode Error"),4:m("Source Not Supported"),5:m("Encryption Error")},Jd={2:m("A network error caused the media download to fail."),3:m("A media error caused playback to be aborted. The media could be corrupt or your browser does not support this format."),4:m("An unsupported error occurred. The server or network failed, or your browser does not support this format."),5:m("The media is encrypted and there are no keys to decrypt it.")},$a=t=>{var e,i;return t.code===1?null:{title:(e=Xd[t.code])!=null?e:`Error ${t.code}`,message:(i=Jd[t.code])!=null?i:t.message}}});function ic(t){return`
    <style>
      :host {
        background: rgb(20 20 30 / .8);
      }

      #content {
        display: block;
        padding: 1.2em 1.5em;
      }

      h3,
      p {
        margin-block: 0 .3em;
      }
    </style>
    <slot name="error-${t.mediaerrorcode}" id="content">
      ${Fn({code:+t.mediaerrorcode,message:t.mediaerrormessage})}
    </slot>
  `}function ac(t){return t.code&&$a(t)!==null}function Fn(t){var e;let{title:i,message:a}=(e=$a(t))!=null?e:{},r="";return i&&(r+=`<slot name="error-${t.code}-title"><h3>${i}</h3></slot>`),a&&(r+=`<slot name="error-${t.code}-message"><p>${a}</p></slot>`),r}var Hn,jd,ec,tc,Wa,Nn,bi,Bn=b(()=>{L();C();Pn();Sa();U();Hn=(t,e,i)=>{if(!e.has(t))throw TypeError("Cannot "+i)},jd=(t,e,i)=>(Hn(t,e,"read from private field"),i?i.call(t):e.get(t)),ec=(t,e,i)=>{if(e.has(t))throw TypeError("Cannot add the same private member more than once");e instanceof WeakSet?e.add(t):e.set(t,i)},tc=(t,e,i,a)=>(Hn(t,e,"write to private field"),a?a.call(t,i):e.set(t,i),i);Nn=[o.MEDIA_ERROR_CODE,o.MEDIA_ERROR_MESSAGE],bi=class extends ye{constructor(){super(...arguments),ec(this,Wa,null)}static get observedAttributes(){return[...super.observedAttributes,...Nn]}formatErrorMessage(e){return this.constructor.formatErrorMessage(e)}attributeChangedCallback(e,i,a){var r;if(super.attributeChangedCallback(e,i,a),!Nn.includes(e))return;let s=(r=this.mediaError)!=null?r:{code:this.mediaErrorCode,message:this.mediaErrorMessage};if(this.open=ac(s),this.open&&(this.shadowRoot.querySelector("slot").name=`error-${this.mediaErrorCode}`,this.shadowRoot.querySelector("#content").innerHTML=this.formatErrorMessage(s),!this.hasAttribute("aria-label"))){let{title:l}=$a(s);l&&this.setAttribute("aria-label",l)}}get mediaError(){return jd(this,Wa)}set mediaError(e){tc(this,Wa,e)}get mediaErrorCode(){return x(this,"mediaerrorcode")}set mediaErrorCode(e){H(this,"mediaerrorcode",e)}get mediaErrorMessage(){return D(this,"mediaerrormessage")}set mediaErrorMessage(e){R(this,"mediaerrormessage",e)}};Wa=new WeakMap;bi.getSlotTemplateHTML=ic;bi.formatErrorMessage=Fn;n.customElements.get("media-error-dialog")||n.customElements.define("media-error-dialog",bi)});function oc(t){return`
    <style>
      :host {
        position: fixed;
        top: 0;
        left: 0;
        z-index: 9999;
        background: rgb(20 20 30 / .8);
        backdrop-filter: blur(10px);
      }

      #content {
        display: block;
        width: clamp(400px, 40vw, 700px);
        max-width: 90vw;
        text-align: left;
      }

      h2 {
        margin: 0 0 1.5rem 0;
        font-size: 1.5rem;
        font-weight: 500;
        text-align: center;
      }

      .shortcuts-table {
        width: 100%;
        border-collapse: collapse;
      }

      .shortcuts-table tr {
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
      }

      .shortcuts-table tr:last-child {
        border-bottom: none;
      }

      .shortcuts-table td {
        padding: 0.75rem 0.5rem;
      }

      .shortcuts-table td:first-child {
        text-align: right;
        padding-right: 1rem;
        width: 40%;
        min-width: 120px;
      }

      .shortcuts-table td:last-child {
        padding-left: 1rem;
      }

      .key {
        display: inline-block;
        background: rgba(255, 255, 255, 0.15);
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 4px;
        padding: 0.25rem 0.5rem;
        font-family: 'Courier New', monospace;
        font-size: 0.9rem;
        font-weight: 500;
        min-width: 1.5rem;
        text-align: center;
        margin: 0 0.2rem;
      }

      .description {
        color: rgba(255, 255, 255, 0.9);
        font-size: 0.95rem;
      }

      .key-combo {
        display: flex;
        align-items: center;
        justify-content: flex-end;
        gap: 0.3rem;
      }

      .key-separator {
        color: rgba(255, 255, 255, 0.5);
        font-size: 0.9rem;
      }
    </style>
    <slot id="content">
      ${sc()}
    </slot>
  `}function sc(){return`
    <h2>Keyboard Shortcuts</h2>
    <table class="shortcuts-table">${[{keys:["Space","k"],description:"Toggle Playback"},{keys:["m"],description:"Toggle mute"},{keys:["f"],description:"Toggle fullscreen"},{keys:["c"],description:"Toggle captions or subtitles, if available"},{keys:["p"],description:"Toggle Picture in Picture"},{keys:["\u2190","j"],description:"Seek back 10s"},{keys:["\u2192","l"],description:"Seek forward 10s"},{keys:["\u2191"],description:"Turn volume up"},{keys:["\u2193"],description:"Turn volume down"},{keys:["< (SHIFT+,)"],description:"Decrease playback rate"},{keys:["> (SHIFT+.)"],description:"Increase playback rate"}].map(({keys:i,description:a})=>`
      <tr>
        <td>
          <div class="key-combo">${i.map((s,l)=>l>0?`<span class="key-separator">or</span><span class="key">${s}</span>`:`<span class="key">${s}</span>`).join("")}</div>
        </td>
        <td class="description">${a}</td>
      </tr>
    `).join("")}</table>
  `}var rc,Qe,$n,Ht,Ft,Va,Wn=b(()=>{L();Sa();rc=(t,e,i)=>{if(!e.has(t))throw TypeError("Cannot "+i)},Qe=(t,e,i)=>(rc(t,e,"read from private field"),i?i.call(t):e.get(t)),$n=(t,e,i)=>{if(e.has(t))throw TypeError("Cannot add the same private member more than once");e instanceof WeakSet?e.add(t):e.set(t,i)};Va=class extends ye{constructor(){super(...arguments),$n(this,Ht,e=>{var i;if(!this.open)return;let a=(i=this.shadowRoot)==null?void 0:i.querySelector("#content");if(!a)return;let r=e.composedPath(),s=r[0]===this||r.includes(this),l=r.includes(a);s&&!l&&(this.open=!1)}),$n(this,Ft,e=>{if(!this.open)return;let i=e.shiftKey&&(e.key==="/"||e.key==="?");(e.key==="Escape"||i)&&!e.ctrlKey&&!e.altKey&&!e.metaKey&&(this.open=!1,e.preventDefault(),e.stopPropagation())})}connectedCallback(){super.connectedCallback(),this.open&&(this.addEventListener("click",Qe(this,Ht)),document.addEventListener("keydown",Qe(this,Ft)))}disconnectedCallback(){this.removeEventListener("click",Qe(this,Ht)),document.removeEventListener("keydown",Qe(this,Ft))}attributeChangedCallback(e,i,a){super.attributeChangedCallback(e,i,a),e==="open"&&(this.open?(this.addEventListener("click",Qe(this,Ht)),document.addEventListener("keydown",Qe(this,Ft))):(this.removeEventListener("click",Qe(this,Ht)),document.removeEventListener("keydown",Qe(this,Ft))))}};Ht=new WeakMap;Ft=new WeakMap;Va.getSlotTemplateHTML=oc;n.customElements.get("media-keyboard-shortcuts-dialog")||n.customElements.define("media-keyboard-shortcuts-dialog",Va)});function hc(t){return`
    <style>
      :host([${o.MEDIA_IS_FULLSCREEN}]) slot[name=icon] slot:not([name=exit]) {
        display: none !important;
      }

      
      :host(:not([${o.MEDIA_IS_FULLSCREEN}])) slot[name=icon] slot:not([name=enter]) {
        display: none !important;
      }

      :host([${o.MEDIA_IS_FULLSCREEN}]) slot[name=tooltip-enter],
      :host(:not([${o.MEDIA_IS_FULLSCREEN}])) slot[name=tooltip-exit] {
        display: none;
      }
    </style>

    <slot name="icon">
      <slot name="enter">${cc}</slot>
      <slot name="exit">${uc}</slot>
    </slot>
  `}function mc(){return`
    <slot name="tooltip-enter">${m("Enter fullscreen mode")}</slot>
    <slot name="tooltip-exit">${m("Exit fullscreen mode")}</slot>
  `}var Kn,nc,lc,dc,Ka,cc,uc,Vn,Ai,Gn=b(()=>{oe();L();C();W();U();Kn=(t,e,i)=>{if(!e.has(t))throw TypeError("Cannot "+i)},nc=(t,e,i)=>(Kn(t,e,"read from private field"),i?i.call(t):e.get(t)),lc=(t,e,i)=>{if(e.has(t))throw TypeError("Cannot add the same private member more than once");e instanceof WeakSet?e.add(t):e.set(t,i)},dc=(t,e,i,a)=>(Kn(t,e,"write to private field"),a?a.call(t,i):e.set(t,i),i),cc=`<svg aria-hidden="true" viewBox="0 0 26 24">
  <path d="M16 3v2.5h3.5V9H22V3h-6ZM4 9h2.5V5.5H10V3H4v6Zm15.5 9.5H16V21h6v-6h-2.5v3.5ZM6.5 15H4v6h6v-2.5H6.5V15Z"/>
</svg>`,uc=`<svg aria-hidden="true" viewBox="0 0 26 24">
  <path d="M18.5 6.5V3H16v6h6V6.5h-3.5ZM16 21h2.5v-3.5H22V15h-6v6ZM4 17.5h3.5V21H10v-6H4v2.5Zm3.5-11H4V9h6V3H7.5v3.5Z"/>
</svg>`;Vn=t=>{let e=t.mediaIsFullscreen?m("exit fullscreen mode"):m("enter fullscreen mode");t.setAttribute("aria-label",e)},Ai=class extends P{constructor(){super(...arguments),lc(this,Ka,null)}static get observedAttributes(){return[...super.observedAttributes,o.MEDIA_IS_FULLSCREEN,o.MEDIA_FULLSCREEN_UNAVAILABLE]}connectedCallback(){super.connectedCallback(),Vn(this)}attributeChangedCallback(e,i,a){super.attributeChangedCallback(e,i,a),e===o.MEDIA_IS_FULLSCREEN&&Vn(this)}get mediaFullscreenUnavailable(){return D(this,o.MEDIA_FULLSCREEN_UNAVAILABLE)}set mediaFullscreenUnavailable(e){R(this,o.MEDIA_FULLSCREEN_UNAVAILABLE,e)}get mediaIsFullscreen(){return _(this,o.MEDIA_IS_FULLSCREEN)}set mediaIsFullscreen(e){g(this,o.MEDIA_IS_FULLSCREEN,e)}handleClick(e){dc(this,Ka,e);let i=nc(this,Ka)instanceof PointerEvent,a=this.mediaIsFullscreen?new n.CustomEvent(h.MEDIA_EXIT_FULLSCREEN_REQUEST,{composed:!0,bubbles:!0}):new n.CustomEvent(h.MEDIA_ENTER_FULLSCREEN_REQUEST,{composed:!0,bubbles:!0,detail:i});this.dispatchEvent(a)}};Ka=new WeakMap;Ai.getSlotTemplateHTML=hc;Ai.getTooltipContentHTML=mc;n.customElements.get("media-fullscreen-button")||n.customElements.define("media-fullscreen-button",Ai)});function fc(t){return`
    <style>
      :host { --media-tooltip-display: none; }
      
      slot[name=indicator] > *,
      :host ::slotted([slot=indicator]) {
        
        min-width: auto;
        fill: var(--media-live-button-icon-color, rgb(140, 140, 140));
        color: var(--media-live-button-icon-color, rgb(140, 140, 140));
      }

      :host([${Ga}]:not([${Ti}])) slot[name=indicator] > *,
      :host([${Ga}]:not([${Ti}])) ::slotted([slot=indicator]) {
        fill: var(--media-live-button-indicator-color, rgb(255, 0, 0));
        color: var(--media-live-button-indicator-color, rgb(255, 0, 0));
      }

      :host([${Ga}]:not([${Ti}])) {
        cursor: var(--media-cursor, not-allowed);
      }

      slot[name=text]{
        text-transform: uppercase;
      }

    </style>

    <slot name="indicator">${vc}</slot>
    
    <slot name="spacer">&nbsp;</slot><slot name="text">${m("live")}</slot>
  `}var Ga,Ti,pc,Ec,vc,qn,qa,Yn=b(()=>{oe();L();C();U();W();({MEDIA_TIME_IS_LIVE:Ga,MEDIA_PAUSED:Ti}=o),{MEDIA_SEEK_TO_LIVE_REQUEST:pc,MEDIA_PLAY_REQUEST:Ec}=h,vc='<svg viewBox="0 0 6 12" aria-hidden="true"><circle cx="3" cy="6" r="2"></circle></svg>';qn=t=>{var e;let i=t.mediaPaused||!t.mediaTimeIsLive,a=i?m("seek to live"):m("playing live");t.setAttribute("aria-label",a);let r=(e=t.shadowRoot)==null?void 0:e.querySelector('slot[name="text"]');r&&(r.textContent=m("live")),i?t.removeAttribute("aria-disabled"):t.setAttribute("aria-disabled","true")},qa=class extends P{static get observedAttributes(){return[...super.observedAttributes,Ga,Ti]}connectedCallback(){super.connectedCallback(),qn(this)}attributeChangedCallback(e,i,a){super.attributeChangedCallback(e,i,a),qn(this)}get mediaPaused(){return _(this,o.MEDIA_PAUSED)}set mediaPaused(e){g(this,o.MEDIA_PAUSED,e)}get mediaTimeIsLive(){return _(this,o.MEDIA_TIME_IS_LIVE)}set mediaTimeIsLive(e){g(this,o.MEDIA_TIME_IS_LIVE,e)}handleClick(){!this.mediaPaused&&this.mediaTimeIsLive||(this.dispatchEvent(new n.CustomEvent(pc,{composed:!0,bubbles:!0})),this.hasAttribute(Ti)&&this.dispatchEvent(new n.CustomEvent(Ec,{composed:!0,bubbles:!0})))}};qa.getSlotTemplateHTML=fc;n.customElements.get("media-live-button")||n.customElements.define("media-live-button",qa)});function gc(t){return`
    <style>
      :host {
        display: var(--media-control-display, var(--media-loading-indicator-display, inline-block));
        vertical-align: middle;
        box-sizing: border-box;
        --_loading-indicator-delay: var(--media-loading-indicator-transition-delay, ${Zn}ms);
      }

      #status {
        color: rgba(0,0,0,0);
        width: 0px;
        height: 0px;
      }

      :host slot[name=icon] > *,
      :host ::slotted([slot=icon]) {
        opacity: var(--media-loading-indicator-opacity, 0);
        transition: opacity 0.15s;
      }

      :host([${o.MEDIA_LOADING}]:not([${o.MEDIA_PAUSED}])) slot[name=icon] > *,
      :host([${o.MEDIA_LOADING}]:not([${o.MEDIA_PAUSED}])) ::slotted([slot=icon]) {
        opacity: var(--media-loading-indicator-opacity, 1);
        transition: opacity 0.15s var(--_loading-indicator-delay);
      }

      :host #status {
        visibility: var(--media-loading-indicator-opacity, hidden);
        transition: visibility 0.15s;
      }

      :host([${o.MEDIA_LOADING}]:not([${o.MEDIA_PAUSED}])) #status {
        visibility: var(--media-loading-indicator-opacity, visible);
        transition: visibility 0.15s var(--_loading-indicator-delay);
      }

      svg, img, ::slotted(svg), ::slotted(img) {
        width: var(--media-loading-indicator-icon-width);
        height: var(--media-loading-indicator-icon-height, 100px);
        fill: var(--media-icon-color, var(--media-primary-color, rgb(238 238 238)));
        vertical-align: middle;
      }
    </style>

    <slot name="icon">${_c}</slot>
    <div id="status" role="status" aria-live="polite">${m("media loading")}</div>
  `}var zn,Ii,Qn,Si,De,Qa,Ya,Zn,_c,Mi,Xn=b(()=>{C();L();U();W();zn=(t,e,i)=>{if(!e.has(t))throw TypeError("Cannot "+i)},Ii=(t,e,i)=>(zn(t,e,"read from private field"),i?i.call(t):e.get(t)),Qn=(t,e,i)=>{if(e.has(t))throw TypeError("Cannot add the same private member more than once");e instanceof WeakSet?e.add(t):e.set(t,i)},Si=(t,e,i,a)=>(zn(t,e,"write to private field"),a?a.call(t,i):e.set(t,i),i),Ya={LOADING_DELAY:"loadingdelay",NO_AUTOHIDE:"noautohide"},Zn=500,_c=`
<svg aria-hidden="true" viewBox="0 0 100 100">
  <path d="M73,50c0-12.7-10.3-23-23-23S27,37.3,27,50 M30.9,50c0-10.5,8.5-19.1,19.1-19.1S69.1,39.5,69.1,50">
    <animateTransform
       attributeName="transform"
       attributeType="XML"
       type="rotate"
       dur="1s"
       from="0 50 50"
       to="360 50 50"
       repeatCount="indefinite" />
  </path>
</svg>
`;Mi=class extends n.HTMLElement{constructor(){if(super(),Qn(this,De,void 0),Qn(this,Qa,Zn),!this.shadowRoot){this.attachShadow(this.constructor.shadowRootOptions);let e=K(this.attributes);this.shadowRoot.innerHTML=this.constructor.getTemplateHTML(e)}}static get observedAttributes(){return[k.MEDIA_CONTROLLER,o.MEDIA_PAUSED,o.MEDIA_LOADING,Ya.LOADING_DELAY]}attributeChangedCallback(e,i,a){var r,s,l,d,c;e===Ya.LOADING_DELAY&&i!==a?this.loadingDelay=Number(a):e===k.MEDIA_CONTROLLER&&(i&&((s=(r=Ii(this,De))==null?void 0:r.unassociateElement)==null||s.call(r,this),Si(this,De,null)),a&&this.isConnected&&(Si(this,De,(l=this.getRootNode())==null?void 0:l.getElementById(a)),(c=(d=Ii(this,De))==null?void 0:d.associateElement)==null||c.call(d,this)))}connectedCallback(){var e,i,a;let r=this.getAttribute(k.MEDIA_CONTROLLER);r&&(Si(this,De,(e=this.getRootNode())==null?void 0:e.getElementById(r)),(a=(i=Ii(this,De))==null?void 0:i.associateElement)==null||a.call(i,this))}disconnectedCallback(){var e,i;(i=(e=Ii(this,De))==null?void 0:e.unassociateElement)==null||i.call(e,this),Si(this,De,null)}get loadingDelay(){return Ii(this,Qa)}set loadingDelay(e){Si(this,Qa,e);let{style:i}=F(this.shadowRoot,":host");i.setProperty("--_loading-indicator-delay",`var(--media-loading-indicator-transition-delay, ${e}ms)`)}get mediaPaused(){return _(this,o.MEDIA_PAUSED)}set mediaPaused(e){g(this,o.MEDIA_PAUSED,e)}get mediaLoading(){return _(this,o.MEDIA_LOADING)}set mediaLoading(e){g(this,o.MEDIA_LOADING,e)}get mediaController(){return D(this,k.MEDIA_CONTROLLER)}set mediaController(e){R(this,k.MEDIA_CONTROLLER,e)}get noAutohide(){return _(this,Ya.NO_AUTOHIDE)}set noAutohide(e){g(this,Ya.NO_AUTOHIDE,e)}};De=new WeakMap;Qa=new WeakMap;Mi.shadowRootOptions={mode:"open"};Mi.getTemplateHTML=gc;n.customElements.get("media-loading-indicator")||n.customElements.define("media-loading-indicator",Mi)});function Tc(t){return`
    <style>
      :host(:not([${o.MEDIA_VOLUME_LEVEL}])) slot[name=icon] slot:not([name=high]),
      :host([${o.MEDIA_VOLUME_LEVEL}=high]) slot[name=icon] slot:not([name=high]) {
        display: none !important;
      }

      :host([${o.MEDIA_VOLUME_LEVEL}=off]) slot[name=icon] slot:not([name=off]) {
        display: none !important;
      }

      :host([${o.MEDIA_VOLUME_LEVEL}=low]) slot[name=icon] slot:not([name=low]) {
        display: none !important;
      }

      :host([${o.MEDIA_VOLUME_LEVEL}=medium]) slot[name=icon] slot:not([name=medium]) {
        display: none !important;
      }

      :host(:not([${o.MEDIA_VOLUME_LEVEL}=off])) slot[name=tooltip-unmute],
      :host([${o.MEDIA_VOLUME_LEVEL}=off]) slot[name=tooltip-mute] {
        display: none;
      }
    </style>

    <slot name="icon">
      <slot name="off">${bc}</slot>
      <slot name="low">${Jn}</slot>
      <slot name="medium">${Jn}</slot>
      <slot name="high">${Ac}</slot>
    </slot>
  `}function Ic(){return`
    <slot name="tooltip-mute">${m("Mute")}</slot>
    <slot name="tooltip-unmute">${m("Unmute")}</slot>
  `}var bc,Jn,Ac,jn,yi,el=b(()=>{oe();L();C();W();U();bc=`<svg aria-hidden="true" viewBox="0 0 24 24">
  <path d="M16.5 12A4.5 4.5 0 0 0 14 8v2.18l2.45 2.45a4.22 4.22 0 0 0 .05-.63Zm2.5 0a6.84 6.84 0 0 1-.54 2.64L20 16.15A8.8 8.8 0 0 0 21 12a9 9 0 0 0-7-8.77v2.06A7 7 0 0 1 19 12ZM4.27 3 3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25A6.92 6.92 0 0 1 14 18.7v2.06A9 9 0 0 0 17.69 19l2 2.05L21 19.73l-9-9L4.27 3ZM12 4 9.91 6.09 12 8.18V4Z"/>
</svg>`,Jn=`<svg aria-hidden="true" viewBox="0 0 24 24">
  <path d="M3 9v6h4l5 5V4L7 9H3Zm13.5 3A4.5 4.5 0 0 0 14 8v8a4.47 4.47 0 0 0 2.5-4Z"/>
</svg>`,Ac=`<svg aria-hidden="true" viewBox="0 0 24 24">
  <path d="M3 9v6h4l5 5V4L7 9H3Zm13.5 3A4.5 4.5 0 0 0 14 8v8a4.47 4.47 0 0 0 2.5-4ZM14 3.23v2.06a7 7 0 0 1 0 13.42v2.06a9 9 0 0 0 0-17.54Z"/>
</svg>`;jn=t=>{let i=t.mediaVolumeLevel==="off"?m("unmute"):m("mute");t.setAttribute("aria-label",i)},yi=class extends P{static get observedAttributes(){return[...super.observedAttributes,o.MEDIA_VOLUME_LEVEL]}connectedCallback(){super.connectedCallback(),jn(this)}attributeChangedCallback(e,i,a){super.attributeChangedCallback(e,i,a),e===o.MEDIA_VOLUME_LEVEL&&jn(this)}get mediaVolumeLevel(){return D(this,o.MEDIA_VOLUME_LEVEL)}set mediaVolumeLevel(e){R(this,o.MEDIA_VOLUME_LEVEL,e)}handleClick(){let e=this.mediaVolumeLevel==="off"?h.MEDIA_UNMUTE_REQUEST:h.MEDIA_MUTE_REQUEST;this.dispatchEvent(new n.CustomEvent(e,{composed:!0,bubbles:!0}))}};yi.getSlotTemplateHTML=Tc;yi.getTooltipContentHTML=Ic;n.customElements.get("media-mute-button")||n.customElements.define("media-mute-button",yi)});function Sc(t){return`
    <style>
      :host([${o.MEDIA_IS_PIP}]) slot[name=icon] slot:not([name=exit]) {
        display: none !important;
      }

      :host(:not([${o.MEDIA_IS_PIP}])) slot[name=icon] slot:not([name=enter]) {
        display: none !important;
      }

      :host([${o.MEDIA_IS_PIP}]) slot[name=tooltip-enter],
      :host(:not([${o.MEDIA_IS_PIP}])) slot[name=tooltip-exit] {
        display: none;
      }
    </style>

    <slot name="icon">
      <slot name="enter">${tl}</slot>
      <slot name="exit">${tl}</slot>
    </slot>
  `}function Mc(){return`
    <slot name="tooltip-enter">${m("Enter picture in picture mode")}</slot>
    <slot name="tooltip-exit">${m("Exit picture in picture mode")}</slot>
  `}var tl,il,ki,al=b(()=>{oe();L();C();W();U();tl=`<svg aria-hidden="true" viewBox="0 0 28 24">
  <path d="M24 3H4a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h20a1 1 0 0 0 1-1V4a1 1 0 0 0-1-1Zm-1 16H5V5h18v14Zm-3-8h-7v5h7v-5Z"/>
</svg>`;il=t=>{let e=t.mediaIsPip?m("exit picture in picture mode"):m("enter picture in picture mode");t.setAttribute("aria-label",e)},ki=class extends P{static get observedAttributes(){return[...super.observedAttributes,o.MEDIA_IS_PIP,o.MEDIA_PIP_UNAVAILABLE]}connectedCallback(){super.connectedCallback(),il(this)}attributeChangedCallback(e,i,a){super.attributeChangedCallback(e,i,a),e===o.MEDIA_IS_PIP&&il(this)}get mediaPipUnavailable(){return D(this,o.MEDIA_PIP_UNAVAILABLE)}set mediaPipUnavailable(e){R(this,o.MEDIA_PIP_UNAVAILABLE,e)}get mediaIsPip(){return _(this,o.MEDIA_IS_PIP)}set mediaIsPip(e){g(this,o.MEDIA_IS_PIP,e)}handleClick(){let e=this.mediaIsPip?h.MEDIA_EXIT_PIP_REQUEST:h.MEDIA_ENTER_PIP_REQUEST;this.dispatchEvent(new n.CustomEvent(e,{composed:!0,bubbles:!0}))}};ki.getSlotTemplateHTML=Sc;ki.getTooltipContentHTML=Mc;n.customElements.get("media-pip-button")||n.customElements.define("media-pip-button",ki)});function Eo(t){return Math.round(t*100)/100}function wc(t){return`
    <style>
      :host {
        min-width: 5ch;
        padding: var(--media-button-padding, var(--media-control-padding, 10px 5px));
      }
    </style>
    <slot name="icon">${t.mediaplaybackrate?Eo(+t.mediaplaybackrate):Li}x</slot>
  `}function Rc(){return m("Playback rate")}var yc,Bt,kc,ze,po,Lc,Li,wi,rl=b(()=>{oe();L();C();Or();U();W();yc=(t,e,i)=>{if(!e.has(t))throw TypeError("Cannot "+i)},Bt=(t,e,i)=>(yc(t,e,"read from private field"),i?i.call(t):e.get(t)),kc=(t,e,i)=>{if(e.has(t))throw TypeError("Cannot add the same private member more than once");e instanceof WeakSet?e.add(t):e.set(t,i)},po={RATES:"rates"},Lc=[1,1.2,1.5,1.7,2],Li=1;wi=class extends P{constructor(){var e;super(),kc(this,ze,new Lt(this,po.RATES,{defaultValue:Lc})),this.container=this.shadowRoot.querySelector('slot[name="icon"]'),this.container.innerHTML=`${Eo((e=this.mediaPlaybackRate)!=null?e:Li)}x`}static get observedAttributes(){return[...super.observedAttributes,o.MEDIA_PLAYBACK_RATE,po.RATES]}attributeChangedCallback(e,i,a){if(super.attributeChangedCallback(e,i,a),e===po.RATES&&(Bt(this,ze).value=a),e===o.MEDIA_PLAYBACK_RATE){let r=a?+a:Number.NaN,s=Eo(Number.isNaN(r)?Li:r);this.container.innerHTML=`${s}x`,this.setAttribute("aria-label",m("Playback rate {playbackRate}",{playbackRate:s}))}}get rates(){return Bt(this,ze)}set rates(e){e?Array.isArray(e)?Bt(this,ze).value=e.join(" "):typeof e=="string"&&(Bt(this,ze).value=e):Bt(this,ze).value=""}get mediaPlaybackRate(){return x(this,o.MEDIA_PLAYBACK_RATE,Li)}set mediaPlaybackRate(e){H(this,o.MEDIA_PLAYBACK_RATE,e)}handleClick(){var e,i;let a=Array.from(Bt(this,ze).values(),l=>+l).sort((l,d)=>l-d),r=(i=(e=a.find(l=>l>this.mediaPlaybackRate))!=null?e:a[0])!=null?i:Li,s=new n.CustomEvent(h.MEDIA_PLAYBACK_RATE_REQUEST,{composed:!0,bubbles:!0,detail:r});this.dispatchEvent(s)}};ze=new WeakMap;wi.getSlotTemplateHTML=wc;wi.getTooltipContentHTML=Rc;n.customElements.get("media-playback-rate-button")||n.customElements.define("media-playback-rate-button",wi)});function Oc(t){return`
    <style>
      :host([${o.MEDIA_PAUSED}]) slot[name=pause],
      :host(:not([${o.MEDIA_PAUSED}])) slot[name=play] {
        display: none !important;
      }

      :host([${o.MEDIA_PAUSED}]) slot[name=tooltip-pause],
      :host(:not([${o.MEDIA_PAUSED}])) slot[name=tooltip-play] {
        display: none;
      }
    </style>

    <slot name="icon">
      <slot name="play">${Dc}</slot>
      <slot name="pause">${Cc}</slot>
    </slot>
  `}function Uc(){return`
    <slot name="tooltip-play">${m("Play")}</slot>
    <slot name="tooltip-pause">${m("Pause")}</slot>
  `}var Dc,Cc,ol,Ri,sl=b(()=>{oe();L();C();W();U();Dc=`<svg aria-hidden="true" viewBox="0 0 24 24">
  <path d="m6 21 15-9L6 3v18Z"/>
</svg>`,Cc=`<svg aria-hidden="true" viewBox="0 0 24 24">
  <path d="M6 20h4V4H6v16Zm8-16v16h4V4h-4Z"/>
</svg>`;ol=t=>{let e=t.mediaPaused?m("play"):m("pause");t.setAttribute("aria-label",e)},Ri=class extends P{static get observedAttributes(){return[...super.observedAttributes,o.MEDIA_PAUSED,o.MEDIA_ENDED]}connectedCallback(){super.connectedCallback(),ol(this)}attributeChangedCallback(e,i,a){super.attributeChangedCallback(e,i,a),(e===o.MEDIA_PAUSED||e===o.MEDIA_LANG)&&ol(this)}get mediaPaused(){return _(this,o.MEDIA_PAUSED)}set mediaPaused(e){g(this,o.MEDIA_PAUSED,e)}handleClick(){let e=this.mediaPaused?h.MEDIA_PLAY_REQUEST:h.MEDIA_PAUSE_REQUEST;this.dispatchEvent(new n.CustomEvent(e,{composed:!0,bubbles:!0}))}};Ri.getSlotTemplateHTML=Oc;Ri.getTooltipContentHTML=Uc;n.customElements.get("media-play-button")||n.customElements.define("media-play-button",Ri)});function xc(t){return`
    <style>
      :host {
        pointer-events: none;
        display: var(--media-poster-image-display, inline-block);
        box-sizing: border-box;
      }

      img {
        max-width: 100%;
        max-height: 100%;
        min-width: 100%;
        min-height: 100%;
        background-repeat: no-repeat;
        background-position: var(--media-poster-image-background-position, var(--media-object-position, center));
        background-size: var(--media-poster-image-background-size, var(--media-object-fit, contain));
        object-fit: var(--media-object-fit, contain);
        object-position: var(--media-object-position, center);
      }
    </style>

    <img part="poster img" aria-hidden="true" id="image"/>
  `}var Ce,Pc,Nc,Di,nl=b(()=>{L();U();Ce={PLACEHOLDER_SRC:"placeholdersrc",SRC:"src"};Pc=t=>{t.style.removeProperty("background-image")},Nc=(t,e)=>{t.style["background-image"]=`url('${e}')`},Di=class extends n.HTMLElement{static get observedAttributes(){return[Ce.PLACEHOLDER_SRC,Ce.SRC]}constructor(){if(super(),!this.shadowRoot){this.attachShadow(this.constructor.shadowRootOptions);let e=K(this.attributes);this.shadowRoot.innerHTML=this.constructor.getTemplateHTML(e)}this.image=this.shadowRoot.querySelector("#image")}attributeChangedCallback(e,i,a){e===Ce.SRC&&(a==null?this.image.removeAttribute(Ce.SRC):this.image.setAttribute(Ce.SRC,a)),e===Ce.PLACEHOLDER_SRC&&(a==null?Pc(this.image):Nc(this.image,a))}get placeholderSrc(){return D(this,Ce.PLACEHOLDER_SRC)}set placeholderSrc(e){R(this,Ce.SRC,e)}get src(){return D(this,Ce.SRC)}set src(e){R(this,Ce.SRC,e)}};Di.shadowRootOptions={mode:"open"};Di.getTemplateHTML=xc;n.customElements.get("media-poster-image")||n.customElements.define("media-poster-image",Di)});var ll,Hc,Fc,Bc,za,vo,fo=b(()=>{Nt();L();C();U();W();ll=(t,e,i)=>{if(!e.has(t))throw TypeError("Cannot "+i)},Hc=(t,e,i)=>(ll(t,e,"read from private field"),i?i.call(t):e.get(t)),Fc=(t,e,i)=>{if(e.has(t))throw TypeError("Cannot add the same private member more than once");e instanceof WeakSet?e.add(t):e.set(t,i)},Bc=(t,e,i,a)=>(ll(t,e,"write to private field"),a?a.call(t,i):e.set(t,i),i),vo=class extends se{constructor(){super(),Fc(this,za,void 0),Bc(this,za,this.shadowRoot.querySelector("slot"))}static get observedAttributes(){return[...super.observedAttributes,o.MEDIA_PREVIEW_CHAPTER,o.MEDIA_LANG]}attributeChangedCallback(e,i,a){if(super.attributeChangedCallback(e,i,a),(e===o.MEDIA_PREVIEW_CHAPTER||e===o.MEDIA_LANG)&&a!==i&&a!=null)if(Hc(this,za).textContent=a,a!==""){let r=m("chapter: {chapterName}",{chapterName:a});this.setAttribute("aria-valuetext",r)}else this.removeAttribute("aria-valuetext")}get mediaPreviewChapter(){return D(this,o.MEDIA_PREVIEW_CHAPTER)}set mediaPreviewChapter(e){R(this,o.MEDIA_PREVIEW_CHAPTER,e)}};za=new WeakMap;n.customElements.get("media-preview-chapter-display")||n.customElements.define("media-preview-chapter-display",vo)});function Wc(t){return`
    <style>
      :host {
        box-sizing: border-box;
        display: var(--media-control-display, var(--media-preview-thumbnail-display, inline-block));
        overflow: hidden;
      }

      img {
        display: none;
        position: relative;
      }
    </style>
    <img crossorigin loading="eager" decoding="async">
  `}var dl,Za,$c,Xa,Oe,$t,Ja,ja=b(()=>{L();C();U();dl=(t,e,i)=>{if(!e.has(t))throw TypeError("Cannot "+i)},Za=(t,e,i)=>(dl(t,e,"read from private field"),i?i.call(t):e.get(t)),$c=(t,e,i)=>{if(e.has(t))throw TypeError("Cannot add the same private member more than once");e instanceof WeakSet?e.add(t):e.set(t,i)},Xa=(t,e,i,a)=>(dl(t,e,"write to private field"),a?a.call(t,i):e.set(t,i),i);$t=class extends n.HTMLElement{constructor(){if(super(),$c(this,Oe,void 0),!this.shadowRoot){this.attachShadow(this.constructor.shadowRootOptions);let e=K(this.attributes);this.shadowRoot.innerHTML=this.constructor.getTemplateHTML(e)}}static get observedAttributes(){return[k.MEDIA_CONTROLLER,o.MEDIA_PREVIEW_IMAGE,o.MEDIA_PREVIEW_COORDS]}connectedCallback(){var e,i,a;let r=this.getAttribute(k.MEDIA_CONTROLLER);r&&(Xa(this,Oe,(e=this.getRootNode())==null?void 0:e.getElementById(r)),(a=(i=Za(this,Oe))==null?void 0:i.associateElement)==null||a.call(i,this))}disconnectedCallback(){var e,i;(i=(e=Za(this,Oe))==null?void 0:e.unassociateElement)==null||i.call(e,this),Xa(this,Oe,null)}attributeChangedCallback(e,i,a){var r,s,l,d,c;[o.MEDIA_PREVIEW_IMAGE,o.MEDIA_PREVIEW_COORDS].includes(e)&&this.update(),e===k.MEDIA_CONTROLLER&&(i&&((s=(r=Za(this,Oe))==null?void 0:r.unassociateElement)==null||s.call(r,this),Xa(this,Oe,null)),a&&this.isConnected&&(Xa(this,Oe,(l=this.getRootNode())==null?void 0:l.getElementById(a)),(c=(d=Za(this,Oe))==null?void 0:d.associateElement)==null||c.call(d,this)))}get mediaPreviewImage(){return D(this,o.MEDIA_PREVIEW_IMAGE)}set mediaPreviewImage(e){R(this,o.MEDIA_PREVIEW_IMAGE,e)}get mediaPreviewCoords(){let e=this.getAttribute(o.MEDIA_PREVIEW_COORDS);if(e)return e.split(/\s+/).map(i=>+i)}set mediaPreviewCoords(e){if(!e){this.removeAttribute(o.MEDIA_PREVIEW_COORDS);return}this.setAttribute(o.MEDIA_PREVIEW_COORDS,e.join(" "))}update(){let e=this.mediaPreviewCoords,i=this.mediaPreviewImage;if(!(e&&i))return;let[a,r,s,l]=e,d=i.split("#")[0],c=getComputedStyle(this),{maxWidth:y,maxHeight:M,minWidth:I,minHeight:f}=c,p=c.getPropertyValue("--media-preview-thumbnail-object-fit").trim()||"contain",T,v;if(p==="fill"){let Pe=parseInt(y)/s,Ne=parseInt(M)/l,jt=parseInt(I)/s,je=parseInt(f)/l;T=Pe<1?Pe:Math.max(Pe,jt),v=Ne<1?Ne:Math.max(Ne,je)}else{let Pe=Math.min(parseInt(y)/s,parseInt(M)/l),Ne=Math.max(parseInt(I)/s,parseInt(f)/l),je=Pe<1?Pe:Ne>1?Ne:1;T=je,v=je}let{style:w}=F(this.shadowRoot,":host"),S=F(this.shadowRoot,"img").style,te=this.shadowRoot.querySelector("img"),Jt=Math.min(T,v)<1?"min":"max";w.setProperty(`${Jt}-width`,"initial","important"),w.setProperty(`${Jt}-height`,"initial","important"),w.width=`${s*T}px`,w.height=`${l*v}px`;let mt=()=>{S.width=`${this.imgWidth*T}px`,S.height=`${this.imgHeight*v}px`,S.display="block"};te.src!==d&&(te.onload=()=>{this.imgWidth=te.naturalWidth,this.imgHeight=te.naturalHeight,mt(),te.onload=null},te.src=d,mt()),mt(),S.transform=`translate(-${a*T}px, -${r*v}px)`}};Oe=new WeakMap;$t.shadowRootOptions={mode:"open"};$t.getTemplateHTML=Wc;n.customElements.get("media-preview-thumbnail")||n.customElements.define("media-preview-thumbnail",$t);Ja=$t});var ul,cl,Vc,Kc,Ci,_o,go=b(()=>{Nt();L();gt();C();U();ul=(t,e,i)=>{if(!e.has(t))throw TypeError("Cannot "+i)},cl=(t,e,i)=>(ul(t,e,"read from private field"),i?i.call(t):e.get(t)),Vc=(t,e,i)=>{if(e.has(t))throw TypeError("Cannot add the same private member more than once");e instanceof WeakSet?e.add(t):e.set(t,i)},Kc=(t,e,i,a)=>(ul(t,e,"write to private field"),a?a.call(t,i):e.set(t,i),i),_o=class extends se{constructor(){super(),Vc(this,Ci,void 0),Kc(this,Ci,this.shadowRoot.querySelector("slot")),cl(this,Ci).textContent=pe(0)}static get observedAttributes(){return[...super.observedAttributes,o.MEDIA_PREVIEW_TIME]}attributeChangedCallback(e,i,a){super.attributeChangedCallback(e,i,a),e===o.MEDIA_PREVIEW_TIME&&a!=null&&(cl(this,Ci).textContent=pe(parseFloat(a)))}get mediaPreviewTime(){return x(this,o.MEDIA_PREVIEW_TIME)}set mediaPreviewTime(e){H(this,o.MEDIA_PREVIEW_TIME,e)}};Ci=new WeakMap;n.customElements.get("media-preview-time-display")||n.customElements.define("media-preview-time-display",_o)});function qc(t,e){return`
    <slot name="icon">${Gc(e.seekOffset)}</slot>
  `}function Qc(){return m("Seek backward")}var Wt,bo,Gc,Yc,zc,Oi,hl=b(()=>{oe();L();C();U();W();Wt={SEEK_OFFSET:"seekoffset"},bo=30,Gc=t=>`
  <svg aria-hidden="true" viewBox="0 0 20 24">
    <defs>
      <style>.text{font-size:8px;font-family:Arial-BoldMT, Arial;font-weight:700;}</style>
    </defs>
    <text class="text value" transform="translate(2.18 19.87)">${t}</text>
    <path d="M10 6V3L4.37 7 10 10.94V8a5.54 5.54 0 0 1 1.9 10.48v2.12A7.5 7.5 0 0 0 10 6Z"/>
  </svg>`;Yc=(t,e)=>{t.setAttribute("aria-label",m("seek back {seekOffset} seconds",{seekOffset:e}))};zc=0,Oi=class extends P{static get observedAttributes(){return[...super.observedAttributes,o.MEDIA_CURRENT_TIME,Wt.SEEK_OFFSET]}connectedCallback(){super.connectedCallback(),this.seekOffset=x(this,Wt.SEEK_OFFSET,bo)}attributeChangedCallback(e,i,a){super.attributeChangedCallback(e,i,a),Yc(this,this.seekOffset),e===Wt.SEEK_OFFSET&&(this.seekOffset=x(this,Wt.SEEK_OFFSET,bo))}get seekOffset(){return x(this,Wt.SEEK_OFFSET,bo)}set seekOffset(e){H(this,Wt.SEEK_OFFSET,e),this.setAttribute("aria-label",m("seek back {seekOffset} seconds",{seekOffset:this.seekOffset})),Ji(ji(this,"icon"),this.seekOffset)}get mediaCurrentTime(){return x(this,o.MEDIA_CURRENT_TIME,zc)}set mediaCurrentTime(e){H(this,o.MEDIA_CURRENT_TIME,e)}handleClick(){let e=Math.max(this.mediaCurrentTime-this.seekOffset,0),i=new n.CustomEvent(h.MEDIA_SEEK_REQUEST,{composed:!0,bubbles:!0,detail:e});this.dispatchEvent(i)}};Oi.getSlotTemplateHTML=qc;Oi.getTooltipContentHTML=Qc;n.customElements.get("media-seek-backward-button")||n.customElements.define("media-seek-backward-button",Oi)});function Xc(t,e){return`
    <slot name="icon">${Zc(e.seekOffset)}</slot>
  `}function jc(){return m("Seek forward")}var Vt,Ao,Zc,Jc,eu,Ui,ml=b(()=>{oe();L();C();U();W();Vt={SEEK_OFFSET:"seekoffset"},Ao=30,Zc=t=>`
  <svg aria-hidden="true" viewBox="0 0 20 24">
    <defs>
      <style>.text{font-size:8px;font-family:Arial-BoldMT, Arial;font-weight:700;}</style>
    </defs>
    <text class="text value" transform="translate(8.9 19.87)">${t}</text>
    <path d="M10 6V3l5.61 4L10 10.94V8a5.54 5.54 0 0 0-1.9 10.48v2.12A7.5 7.5 0 0 1 10 6Z"/>
  </svg>`;Jc=(t,e)=>{t.setAttribute("aria-label",m("seek forward {seekOffset} seconds",{seekOffset:e}))};eu=0,Ui=class extends P{static get observedAttributes(){return[...super.observedAttributes,o.MEDIA_CURRENT_TIME,Vt.SEEK_OFFSET]}connectedCallback(){super.connectedCallback(),this.seekOffset=x(this,Vt.SEEK_OFFSET,Ao)}attributeChangedCallback(e,i,a){super.attributeChangedCallback(e,i,a),Jc(this,this.seekOffset),e===Vt.SEEK_OFFSET&&(this.seekOffset=x(this,Vt.SEEK_OFFSET,Ao))}get seekOffset(){return x(this,Vt.SEEK_OFFSET,Ao)}set seekOffset(e){H(this,Vt.SEEK_OFFSET,e),this.setAttribute("aria-label",m("seek forward {seekOffset} seconds",{seekOffset:this.seekOffset})),Ji(ji(this,"icon"),this.seekOffset)}get mediaCurrentTime(){return x(this,o.MEDIA_CURRENT_TIME,eu)}set mediaCurrentTime(e){H(this,o.MEDIA_CURRENT_TIME,e)}handleClick(){let e=this.mediaCurrentTime+this.seekOffset,i=new n.CustomEvent(h.MEDIA_SEEK_REQUEST,{composed:!0,bubbles:!0,detail:e});this.dispatchEvent(i)}};Ui.getSlotTemplateHTML=Xc;Ui.getTooltipContentHTML=jc;n.customElements.get("media-seek-forward-button")||n.customElements.define("media-seek-forward-button",Ui)});function au(t,e){return`
    <slot>${Io(e)}</slot>
  `}var So,Ae,ut,Mo,Xe,Kt,Ue,rr,yo,El,ir,ko,xi,er,tr,To,Ze,pl,vl,tu,Io,iu,ru,ar,fl=b(()=>{Nt();U();L();gt();C();W();So=(t,e,i)=>{if(!e.has(t))throw TypeError("Cannot "+i)},Ae=(t,e,i)=>(So(t,e,"read from private field"),i?i.call(t):e.get(t)),ut=(t,e,i)=>{if(e.has(t))throw TypeError("Cannot add the same private member more than once");e instanceof WeakSet?e.add(t):e.set(t,i)},Mo=(t,e,i,a)=>(So(t,e,"write to private field"),a?a.call(t,i):e.set(t,i),i),Xe=(t,e,i)=>(So(t,e,"access private method"),i),Ze={REMAINING:"remaining",SHOW_DURATION:"showduration",NO_TOGGLE:"notoggle"},pl=[...Object.values(Ze),o.MEDIA_CURRENT_TIME,o.MEDIA_DURATION,o.MEDIA_SEEKABLE],vl=["Enter"," "],tu="&nbsp;/&nbsp;",Io=(t,{timesSep:e=tu}={})=>{var i,a;let r=(i=t.mediaCurrentTime)!=null?i:0,[,s]=(a=t.mediaSeekable)!=null?a:[],l=0;Number.isFinite(t.mediaDuration)?l=t.mediaDuration:Number.isFinite(s)&&(l=s);let d=t.remaining?pe(0-(l-r)):pe(r);return t.showDuration?`${d}${e}${pe(l)}`:d},iu=t=>{var e;let i=t.mediaCurrentTime,[,a]=(e=t.mediaSeekable)!=null?e:[],r=null;if(Number.isFinite(t.mediaDuration)?r=t.mediaDuration:Number.isFinite(a)&&(r=a),i==null||r===null){t.setAttribute("aria-description",m("video not loaded, unknown time."));return}let s=t.remaining?tt(0-(r-i)):tt(i);if(!t.showDuration){t.setAttribute("aria-description",s);return}let l=tt(r),d=m("{currentTime} of {totalTime}",{currentTime:s,totalTime:l});t.setAttribute("aria-description",d)};ru=t=>{t.setAttribute("aria-label",m("playback time"))},ar=class extends se{constructor(){super(),ut(this,yo),ut(this,ir),ut(this,xi),ut(this,tr),ut(this,Kt,void 0),ut(this,Ue,null),ut(this,rr,e=>{let{metaKey:i,altKey:a,key:r}=e;if(i||a||!vl.includes(r)){this.removeEventListener("keyup",Ae(this,Ue));return}this.addEventListener("keyup",Ae(this,Ue))}),Mo(this,Kt,this.shadowRoot.querySelector("slot")),Ae(this,Kt).innerHTML=`${Io(this)}`}static get observedAttributes(){return[...super.observedAttributes,...pl,"disabled"]}connectedCallback(){let{style:e}=F(this.shadowRoot,":host(:hover:not([notoggle]))");e.setProperty("cursor","var(--media-cursor, pointer)"),e.setProperty("background","var(--media-control-hover-background, rgba(50 50 70 / .7))"),this.setAttribute("aria-label",m("playback time")),Xe(this,xi,er).call(this),super.connectedCallback()}toggleTimeDisplay(){this.noToggle||(this.hasAttribute("remaining")?this.removeAttribute("remaining"):this.setAttribute("remaining",""))}disconnectedCallback(){this.disable(),Xe(this,ir,ko).call(this),super.disconnectedCallback()}attributeChangedCallback(e,i,a){ru(this),pl.includes(e)?this.update():e==="disabled"&&a!==i?a==null?Xe(this,xi,er).call(this):Xe(this,tr,To).call(this):e===Ze.NO_TOGGLE&&a!==i&&(this.noToggle?Xe(this,tr,To).call(this):Xe(this,xi,er).call(this)),super.attributeChangedCallback(e,i,a)}enable(){this.noToggle||(this.tabIndex=0)}disable(){this.tabIndex=-1}get remaining(){return _(this,Ze.REMAINING)}set remaining(e){g(this,Ze.REMAINING,e)}get showDuration(){return _(this,Ze.SHOW_DURATION)}set showDuration(e){g(this,Ze.SHOW_DURATION,e)}get noToggle(){return _(this,Ze.NO_TOGGLE)}set noToggle(e){g(this,Ze.NO_TOGGLE,e)}get mediaDuration(){return x(this,o.MEDIA_DURATION)}set mediaDuration(e){H(this,o.MEDIA_DURATION,e)}get mediaCurrentTime(){return x(this,o.MEDIA_CURRENT_TIME)}set mediaCurrentTime(e){H(this,o.MEDIA_CURRENT_TIME,e)}get mediaSeekable(){let e=this.getAttribute(o.MEDIA_SEEKABLE);if(e)return e.split(":").map(i=>+i)}set mediaSeekable(e){if(e==null){this.removeAttribute(o.MEDIA_SEEKABLE);return}this.setAttribute(o.MEDIA_SEEKABLE,e.join(":"))}update(){let e=Io(this);iu(this),e!==Ae(this,Kt).innerHTML&&(Ae(this,Kt).innerHTML=e)}};Kt=new WeakMap;Ue=new WeakMap;rr=new WeakMap;yo=new WeakSet;El=function(){Ae(this,Ue)||(Mo(this,Ue,t=>{let{key:e}=t;if(!vl.includes(e)){this.removeEventListener("keyup",Ae(this,Ue));return}this.toggleTimeDisplay()}),this.addEventListener("keydown",Ae(this,rr)),this.addEventListener("click",this.toggleTimeDisplay))};ir=new WeakSet;ko=function(){Ae(this,Ue)&&(this.removeEventListener("keyup",Ae(this,Ue)),this.removeEventListener("keydown",Ae(this,rr)),this.removeEventListener("click",this.toggleTimeDisplay),Mo(this,Ue,null))};xi=new WeakSet;er=function(){!this.noToggle&&!this.hasAttribute("disabled")&&(this.setAttribute("role","button"),this.enable(),Xe(this,yo,El).call(this))};tr=new WeakSet;To=function(){this.removeAttribute("role"),this.disable(),Xe(this,ir,ko).call(this)};ar.getSlotTemplateHTML=au;n.customElements.get("media-time-display")||n.customElements.define("media-time-display",ar)});var _l,J,xe,le,ou,Gt,or,qt,Pi,sr,nr,lr,Yt,ht,dr,cr,gl=b(()=>{_l=(t,e,i)=>{if(!e.has(t))throw TypeError("Cannot "+i)},J=(t,e,i)=>(_l(t,e,"read from private field"),i?i.call(t):e.get(t)),xe=(t,e,i)=>{if(e.has(t))throw TypeError("Cannot add the same private member more than once");e instanceof WeakSet?e.add(t):e.set(t,i)},le=(t,e,i,a)=>(_l(t,e,"write to private field"),a?a.call(t,i):e.set(t,i),i),ou=(t,e,i,a)=>({set _(r){le(t,e,r,i)},get _(){return J(t,e,a)}}),cr=class{constructor(e,i,a){xe(this,Gt,void 0),xe(this,or,void 0),xe(this,qt,void 0),xe(this,Pi,void 0),xe(this,sr,void 0),xe(this,nr,void 0),xe(this,lr,void 0),xe(this,Yt,void 0),xe(this,ht,0),xe(this,dr,(r=performance.now())=>{le(this,ht,requestAnimationFrame(J(this,dr))),le(this,Pi,performance.now()-J(this,qt));let s=1e3/this.fps;if(J(this,Pi)>s){le(this,qt,r-J(this,Pi)%s);let l=1e3/((r-J(this,or))/++ou(this,sr)._),d=(r-J(this,nr))/1e3/this.duration,c=J(this,lr)+d*this.playbackRate;c-J(this,Gt).valueAsNumber>0?le(this,Yt,this.playbackRate/this.duration/l):(le(this,Yt,.995*J(this,Yt)),c=J(this,Gt).valueAsNumber+J(this,Yt)),this.callback(c)}}),le(this,Gt,e),this.callback=i,this.fps=a}start(){J(this,ht)===0&&(le(this,qt,performance.now()),le(this,or,J(this,qt)),le(this,sr,0),J(this,dr).call(this))}stop(){J(this,ht)!==0&&(cancelAnimationFrame(J(this,ht)),le(this,ht,0))}update({start:e,duration:i,playbackRate:a}){let r=e-J(this,Gt).valueAsNumber,s=Math.abs(i-this.duration);(r>0||r<-.5/i||s>=.5)&&this.callback(e),le(this,lr,e),le(this,nr,performance.now()),this.duration=i,this.playbackRate=a}};Gt=new WeakMap;or=new WeakMap;qt=new WeakMap;Pi=new WeakMap;sr=new WeakMap;nr=new WeakMap;lr=new WeakMap;Yt=new WeakMap;ht=new WeakMap;dr=new WeakMap});function nu(t){return`
    <style>
      :host {
        --media-box-border-radius: 4px;
        --media-box-padding-left: 10px;
        --media-box-padding-right: 10px;
        --media-preview-border-radius: var(--media-box-border-radius);
        --media-box-arrow-offset: var(--media-box-border-radius);
        --_control-background: var(--media-control-background, var(--media-secondary-color, rgb(20 20 30 / .7)));
        --_preview-background: var(--media-preview-background, var(--_control-background));

        
        contain: layout;
      }

      #buffered {
        background: var(--media-time-range-buffered-color, rgb(255 255 255 / .4));
        position: absolute;
        height: 100%;
        will-change: width;
      }

      #preview-rail,
      #current-rail {
        width: 100%;
        position: absolute;
        left: 0;
        bottom: 100%;
        pointer-events: none;
        will-change: transform;
      }

      [part~="box"] {
        width: min-content;
        
        position: absolute;
        bottom: 100%;
        flex-direction: column;
        align-items: center;
        transform: translateX(-50%);
      }

      [part~="current-box"] {
        display: var(--media-current-box-display, var(--media-box-display, flex));
        margin: var(--media-current-box-margin, var(--media-box-margin, 0 0 5px));
        visibility: hidden;
      }

      [part~="preview-box"] {
        display: var(--media-preview-box-display, var(--media-box-display, flex));
        margin: var(--media-preview-box-margin, var(--media-box-margin, 0 0 5px));
        transition-property: var(--media-preview-transition-property, visibility, opacity);
        transition-duration: var(--media-preview-transition-duration-out, .25s);
        transition-delay: var(--media-preview-transition-delay-out, 0s);
        visibility: hidden;
        opacity: 0;
      }

      :host(:is([${o.MEDIA_PREVIEW_IMAGE}], [${o.MEDIA_PREVIEW_TIME}])[dragging]) [part~="preview-box"] {
        transition-duration: var(--media-preview-transition-duration-in, .5s);
        transition-delay: var(--media-preview-transition-delay-in, .25s);
        visibility: visible;
        opacity: 1;
      }

      @media (hover: hover) {
        :host(:is([${o.MEDIA_PREVIEW_IMAGE}], [${o.MEDIA_PREVIEW_TIME}]):hover) [part~="preview-box"] {
          transition-duration: var(--media-preview-transition-duration-in, .5s);
          transition-delay: var(--media-preview-transition-delay-in, .25s);
          visibility: visible;
          opacity: 1;
        }
      }

      media-preview-thumbnail,
      ::slotted(media-preview-thumbnail) {
        visibility: hidden;
        
        transition: visibility 0s .25s;
        transition-delay: calc(var(--media-preview-transition-delay-out, 0s) + var(--media-preview-transition-duration-out, .25s));
        background: var(--media-preview-thumbnail-background, var(--_preview-background));
        box-shadow: var(--media-preview-thumbnail-box-shadow, 0 0 4px rgb(0 0 0 / .2));
        max-width: var(--media-preview-thumbnail-max-width, 180px);
        max-height: var(--media-preview-thumbnail-max-height, 160px);
        min-width: var(--media-preview-thumbnail-min-width, 120px);
        min-height: var(--media-preview-thumbnail-min-height, 80px);
        border: var(--media-preview-thumbnail-border);
        border-radius: var(--media-preview-thumbnail-border-radius,
          var(--media-preview-border-radius) var(--media-preview-border-radius) 0 0);
      }

      :host([${o.MEDIA_PREVIEW_IMAGE}][dragging]) media-preview-thumbnail,
      :host([${o.MEDIA_PREVIEW_IMAGE}][dragging]) ::slotted(media-preview-thumbnail) {
        transition-delay: var(--media-preview-transition-delay-in, .25s);
        visibility: visible;
      }

      @media (hover: hover) {
        :host([${o.MEDIA_PREVIEW_IMAGE}]:hover) media-preview-thumbnail,
        :host([${o.MEDIA_PREVIEW_IMAGE}]:hover) ::slotted(media-preview-thumbnail) {
          transition-delay: var(--media-preview-transition-delay-in, .25s);
          visibility: visible;
        }

        :host([${o.MEDIA_PREVIEW_TIME}]:hover) {
          --media-time-range-hover-display: block;
        }
      }

      media-preview-chapter-display,
      ::slotted(media-preview-chapter-display) {
        font-size: var(--media-font-size, 13px);
        line-height: 17px;
        min-width: 0;
        visibility: hidden;
        
        transition: min-width 0s, border-radius 0s, margin 0s, padding 0s, visibility 0s;
        transition-delay: calc(var(--media-preview-transition-delay-out, 0s) + var(--media-preview-transition-duration-out, .25s));
        background: var(--media-preview-chapter-background, var(--_preview-background));
        border-radius: var(--media-preview-chapter-border-radius,
          var(--media-preview-border-radius) var(--media-preview-border-radius)
          var(--media-preview-border-radius) var(--media-preview-border-radius));
        padding: var(--media-preview-chapter-padding, 3.5px 9px);
        margin: var(--media-preview-chapter-margin, 0 0 5px);
        text-shadow: var(--media-preview-chapter-text-shadow, 0 0 4px rgb(0 0 0 / .75));
      }

      :host([${o.MEDIA_PREVIEW_IMAGE}]) media-preview-chapter-display,
      :host([${o.MEDIA_PREVIEW_IMAGE}]) ::slotted(media-preview-chapter-display) {
        transition-delay: var(--media-preview-transition-delay-in, .25s);
        border-radius: var(--media-preview-chapter-border-radius, 0);
        padding: var(--media-preview-chapter-padding, 3.5px 9px 0);
        margin: var(--media-preview-chapter-margin, 0);
        min-width: 100%;
      }

      media-preview-chapter-display[${o.MEDIA_PREVIEW_CHAPTER}],
      ::slotted(media-preview-chapter-display[${o.MEDIA_PREVIEW_CHAPTER}]) {
        visibility: visible;
      }

      media-preview-chapter-display:not([aria-valuetext]),
      ::slotted(media-preview-chapter-display:not([aria-valuetext])) {
        display: none;
      }

      media-preview-time-display,
      ::slotted(media-preview-time-display),
      media-time-display,
      ::slotted(media-time-display) {
        font-size: var(--media-font-size, 13px);
        line-height: 17px;
        min-width: 0;
        
        transition: min-width 0s, border-radius 0s;
        transition-delay: calc(var(--media-preview-transition-delay-out, 0s) + var(--media-preview-transition-duration-out, .25s));
        background: var(--media-preview-time-background, var(--_preview-background));
        border-radius: var(--media-preview-time-border-radius,
          var(--media-preview-border-radius) var(--media-preview-border-radius)
          var(--media-preview-border-radius) var(--media-preview-border-radius));
        padding: var(--media-preview-time-padding, 3.5px 9px);
        margin: var(--media-preview-time-margin, 0);
        text-shadow: var(--media-preview-time-text-shadow, 0 0 4px rgb(0 0 0 / .75));
        transform: translateX(min(
          max(calc(50% - var(--_box-width) / 2),
          calc(var(--_box-shift, 0))),
          calc(var(--_box-width) / 2 - 50%)
        ));
      }

      :host([${o.MEDIA_PREVIEW_IMAGE}]) media-preview-time-display,
      :host([${o.MEDIA_PREVIEW_IMAGE}]) ::slotted(media-preview-time-display) {
        transition-delay: var(--media-preview-transition-delay-in, .25s);
        border-radius: var(--media-preview-time-border-radius,
          0 0 var(--media-preview-border-radius) var(--media-preview-border-radius));
        min-width: 100%;
      }

      :host([${o.MEDIA_PREVIEW_TIME}]:hover) {
        --media-time-range-hover-display: block;
      }

      [part~="arrow"],
      ::slotted([part~="arrow"]) {
        display: var(--media-box-arrow-display, inline-block);
        transform: translateX(min(
          max(calc(50% - var(--_box-width) / 2 + var(--media-box-arrow-offset)),
          calc(var(--_box-shift, 0))),
          calc(var(--_box-width) / 2 - 50% - var(--media-box-arrow-offset))
        ));
        
        border-color: transparent;
        border-top-color: var(--media-box-arrow-background, var(--_control-background));
        border-width: var(--media-box-arrow-border-width,
          var(--media-box-arrow-height, 5px) var(--media-box-arrow-width, 6px) 0);
        border-style: solid;
        justify-content: center;
        height: 0;
      }
    </style>
    <div id="preview-rail">
      <slot name="preview" part="box preview-box">
        <media-preview-thumbnail>
          <template shadowrootmode="${Ja.shadowRootOptions.mode}">
            ${Ja.getTemplateHTML({})}
          </template>
        </media-preview-thumbnail>
        <media-preview-chapter-display></media-preview-chapter-display>
        <media-preview-time-display></media-preview-time-display>
        <slot name="preview-arrow"><div part="arrow"></div></slot>
      </slot>
    </div>
    <div id="current-rail">
      <slot name="current" part="box current-box">
        
      </slot>
    </div>
  `}var Co,B,z,ce,ue,Qt,Je,mr,Hi,pr,hr,Fi,Bi,zt,Zt,Ni,Lo,bl,wo,Er,Oo,vr,Uo,fr,xo,Ro,Al,$i,_r,Do,Tl,su,ur,Il,Wi,Sl=b(()=>{L();xa();ja();go();fo();C();ft();gt();U();gl();U();W();ja();Co=(t,e,i)=>{if(!e.has(t))throw TypeError("Cannot "+i)},B=(t,e,i)=>(Co(t,e,"read from private field"),i?i.call(t):e.get(t)),z=(t,e,i)=>{if(e.has(t))throw TypeError("Cannot add the same private member more than once");e instanceof WeakSet?e.add(t):e.set(t,i)},ce=(t,e,i,a)=>(Co(t,e,"write to private field"),a?a.call(t,i):e.set(t,i),i),ue=(t,e,i)=>(Co(t,e,"access private method"),i),su=t=>{let e=t.range,i=tt(+Il(t)),a=tt(+t.mediaSeekableEnd),r=i&&a?m("{currentTime} of {totalTime}",{currentTime:i,totalTime:a}):m("video not loaded, unknown time.");e.setAttribute("aria-valuetext",r)};ur=(t,e=t.mediaCurrentTime)=>{let i=Number.isFinite(t.mediaSeekableStart)?t.mediaSeekableStart:0,a=Number.isFinite(t.mediaDuration)?t.mediaDuration:t.mediaSeekableEnd;if(Number.isNaN(a))return 0;let r=(e-i)/(a-i);return Math.max(0,Math.min(r,1))},Il=(t,e=t.range.valueAsNumber)=>{let i=Number.isFinite(t.mediaSeekableStart)?t.mediaSeekableStart:0,a=Number.isFinite(t.mediaDuration)?t.mediaDuration:t.mediaSeekableEnd;return Number.isNaN(a)?0:e*(a-i)+i},Wi=class extends Le{constructor(){super(),z(this,Lo),z(this,Er),z(this,vr),z(this,fr),z(this,Ro),z(this,$i),z(this,Do),z(this,Qt,null),z(this,Je,void 0),z(this,mr,void 0),z(this,Hi,void 0),z(this,pr,void 0),z(this,hr,void 0),z(this,Fi,void 0),z(this,Bi,void 0),z(this,zt,void 0),z(this,Zt,void 0),z(this,Ni,()=>{ue(this,Lo,bl).call(this)?B(this,Je).start():B(this,Je).stop()}),z(this,wo,a=>{this.dragging||(vt(a)&&(this.range.valueAsNumber=a),B(this,Zt)||this.updateBar())}),this.shadowRoot.querySelector("#track").insertAdjacentHTML("afterbegin",'<div id="buffered" part="buffered"></div>'),ce(this,mr,this.shadowRoot.querySelectorAll('[part~="box"]')),ce(this,pr,this.shadowRoot.querySelector('[part~="preview-box"]')),ce(this,hr,this.shadowRoot.querySelector('[part~="current-box"]'));let i=getComputedStyle(this);ce(this,Fi,parseInt(i.getPropertyValue("--media-box-padding-left"))),ce(this,Bi,parseInt(i.getPropertyValue("--media-box-padding-right"))),ce(this,Je,new cr(this.range,B(this,wo),60))}static get observedAttributes(){return[...super.observedAttributes,o.MEDIA_PAUSED,o.MEDIA_DURATION,o.MEDIA_SEEKABLE,o.MEDIA_CURRENT_TIME,o.MEDIA_PREVIEW_IMAGE,o.MEDIA_PREVIEW_TIME,o.MEDIA_PREVIEW_CHAPTER,o.MEDIA_BUFFERED,o.MEDIA_PLAYBACK_RATE,o.MEDIA_LOADING,o.MEDIA_ENDED]}connectedCallback(){var e;super.connectedCallback(),this.range.setAttribute("aria-label",m("seek")),B(this,Ni).call(this),ce(this,Qt,this.getRootNode()),(e=B(this,Qt))==null||e.addEventListener("transitionstart",this)}disconnectedCallback(){var e;super.disconnectedCallback(),B(this,Je).stop(),(e=B(this,Qt))==null||e.removeEventListener("transitionstart",this),ce(this,Qt,null)}attributeChangedCallback(e,i,a){super.attributeChangedCallback(e,i,a),i!=a&&(e===o.MEDIA_CURRENT_TIME||e===o.MEDIA_PAUSED||e===o.MEDIA_ENDED||e===o.MEDIA_LOADING||e===o.MEDIA_DURATION||e===o.MEDIA_SEEKABLE?(B(this,Je).update({start:ur(this),duration:this.mediaSeekableEnd-this.mediaSeekableStart,playbackRate:this.mediaPlaybackRate}),B(this,Ni).call(this),su(this)):e===o.MEDIA_BUFFERED&&this.updateBufferedBar(),(e===o.MEDIA_DURATION||e===o.MEDIA_SEEKABLE)&&(this.mediaChaptersCues=B(this,zt),this.updateBar()))}get mediaChaptersCues(){return B(this,zt)}set mediaChaptersCues(e){var i;ce(this,zt,e),this.updateSegments((i=B(this,zt))==null?void 0:i.map(a=>({start:ur(this,a.startTime),end:ur(this,a.endTime)})))}get mediaPaused(){return _(this,o.MEDIA_PAUSED)}set mediaPaused(e){g(this,o.MEDIA_PAUSED,e)}get mediaLoading(){return _(this,o.MEDIA_LOADING)}set mediaLoading(e){g(this,o.MEDIA_LOADING,e)}get mediaDuration(){return x(this,o.MEDIA_DURATION)}set mediaDuration(e){H(this,o.MEDIA_DURATION,e)}get mediaCurrentTime(){return x(this,o.MEDIA_CURRENT_TIME)}set mediaCurrentTime(e){H(this,o.MEDIA_CURRENT_TIME,e)}get mediaPlaybackRate(){return x(this,o.MEDIA_PLAYBACK_RATE,1)}set mediaPlaybackRate(e){H(this,o.MEDIA_PLAYBACK_RATE,e)}get mediaBuffered(){let e=this.getAttribute(o.MEDIA_BUFFERED);return e?e.split(" ").map(i=>i.split(":").map(a=>+a)):[]}set mediaBuffered(e){if(!e){this.removeAttribute(o.MEDIA_BUFFERED);return}let i=e.map(a=>a.join(":")).join(" ");this.setAttribute(o.MEDIA_BUFFERED,i)}get mediaSeekable(){let e=this.getAttribute(o.MEDIA_SEEKABLE);if(e)return e.split(":").map(i=>+i)}set mediaSeekable(e){if(e==null){this.removeAttribute(o.MEDIA_SEEKABLE);return}this.setAttribute(o.MEDIA_SEEKABLE,e.join(":"))}get mediaSeekableEnd(){var e;let[,i=this.mediaDuration]=(e=this.mediaSeekable)!=null?e:[];return i}get mediaSeekableStart(){var e;let[i=0]=(e=this.mediaSeekable)!=null?e:[];return i}get mediaPreviewImage(){return D(this,o.MEDIA_PREVIEW_IMAGE)}set mediaPreviewImage(e){R(this,o.MEDIA_PREVIEW_IMAGE,e)}get mediaPreviewTime(){return x(this,o.MEDIA_PREVIEW_TIME)}set mediaPreviewTime(e){H(this,o.MEDIA_PREVIEW_TIME,e)}get mediaEnded(){return _(this,o.MEDIA_ENDED)}set mediaEnded(e){g(this,o.MEDIA_ENDED,e)}updateBar(){super.updateBar(),this.updateBufferedBar(),this.updateCurrentBox()}updateBufferedBar(){var e;let i=this.mediaBuffered;if(!i.length)return;let a;if(this.mediaEnded)a=1;else{let s=this.mediaCurrentTime,[,l=this.mediaSeekableStart]=(e=i.find(([d,c])=>d<=s&&s<=c))!=null?e:[];a=ur(this,l)}let{style:r}=F(this.shadowRoot,"#buffered");r.setProperty("width",`${a*100}%`)}updateCurrentBox(){if(!this.shadowRoot.querySelector('slot[name="current"]').assignedElements().length)return;let i=F(this.shadowRoot,"#current-rail"),a=F(this.shadowRoot,'[part~="current-box"]'),r=ue(this,Er,Oo).call(this,B(this,hr)),s=ue(this,vr,Uo).call(this,r,this.range.valueAsNumber),l=ue(this,fr,xo).call(this,r,this.range.valueAsNumber);i.style.transform=`translateX(${s})`,i.style.setProperty("--_range-width",`${r.range.width}`),a.style.setProperty("--_box-shift",`${l}`),a.style.setProperty("--_box-width",`${r.box.width}px`),a.style.setProperty("visibility","initial")}handleEvent(e){switch(super.handleEvent(e),e.type){case"input":ue(this,Do,Tl).call(this);break;case"pointermove":ue(this,Ro,Al).call(this,e);break;case"pointerup":B(this,Zt)&&ce(this,Zt,!1);break;case"pointerdown":ce(this,Zt,!0);break;case"pointerleave":ue(this,$i,_r).call(this,null);break;case"transitionstart":Te(e.target,this)&&setTimeout(()=>B(this,Ni).call(this),0);break}}};Qt=new WeakMap;Je=new WeakMap;mr=new WeakMap;Hi=new WeakMap;pr=new WeakMap;hr=new WeakMap;Fi=new WeakMap;Bi=new WeakMap;zt=new WeakMap;Zt=new WeakMap;Ni=new WeakMap;Lo=new WeakSet;bl=function(){return this.isConnected&&!this.mediaPaused&&!this.mediaLoading&&!this.mediaEnded&&this.mediaSeekableEnd>0&&ea(this)};wo=new WeakMap;Er=new WeakSet;Oo=function(t){var e;let a=((e=this.getAttribute("bounds")?We(this,`#${this.getAttribute("bounds")}`):this.parentElement)!=null?e:this).getBoundingClientRect(),r=this.range.getBoundingClientRect(),s=t.offsetWidth,l=-(r.left-a.left-s/2),d=a.right-r.left-s/2;return{box:{width:s,min:l,max:d},bounds:a,range:r}};vr=new WeakSet;Uo=function(t,e){let i=`${e*100}%`,{width:a,min:r,max:s}=t.box;if(!a)return i;if(Number.isNaN(r)||(i=`max(${`calc(1 / var(--_range-width) * 100 * ${r}% + var(--media-box-padding-left))`}, ${i})`),!Number.isNaN(s)){let d=`calc(1 / var(--_range-width) * 100 * ${s}% - var(--media-box-padding-right))`;i=`min(${i}, ${d})`}return i};fr=new WeakSet;xo=function(t,e){let{width:i,min:a,max:r}=t.box,s=e*t.range.width;if(s<a+B(this,Fi)){let l=t.range.left-t.bounds.left-B(this,Fi);return`${s-i/2+l}px`}if(s>r-B(this,Bi)){let l=t.bounds.right-t.range.right-B(this,Bi);return`${s+i/2-l-t.range.width}px`}return 0};Ro=new WeakSet;Al=function(t){let e=[...B(this,mr)].some(M=>t.composedPath().includes(M));if(!this.dragging&&(e||!t.composedPath().includes(this))){ue(this,$i,_r).call(this,null);return}let i=this.mediaSeekableEnd;if(!i)return;let a=F(this.shadowRoot,"#preview-rail"),r=F(this.shadowRoot,'[part~="preview-box"]'),s=ue(this,Er,Oo).call(this,B(this,pr)),l=(t.clientX-s.range.left)/s.range.width;l=Math.max(0,Math.min(1,l));let d=ue(this,vr,Uo).call(this,s,l),c=ue(this,fr,xo).call(this,s,l);a.style.transform=`translateX(${d})`,a.style.setProperty("--_range-width",`${s.range.width}`),r.style.setProperty("--_box-shift",`${c}`),r.style.setProperty("--_box-width",`${s.box.width}px`);let y=Math.round(B(this,Hi))-Math.round(l*i);Math.abs(y)<1&&l>.01&&l<.99||(ce(this,Hi,l*i),ue(this,$i,_r).call(this,B(this,Hi)))};$i=new WeakSet;_r=function(t){this.dispatchEvent(new n.CustomEvent(h.MEDIA_PREVIEW_REQUEST,{composed:!0,bubbles:!0,detail:t}))};Do=new WeakSet;Tl=function(){B(this,Je).stop();let t=Il(this);this.dispatchEvent(new n.CustomEvent(h.MEDIA_SEEK_REQUEST,{composed:!0,bubbles:!0,detail:t}))};Wi.shadowRootOptions={mode:"open"};Wi.getContainerTemplateHTML=nu;n.customElements.get("media-time-range")||n.customElements.define("media-time-range",Wi)});var lu,Ml,du,gr,cu,uu,hu,Po,yl=b(()=>{L();xa();C();W();U();lu=(t,e,i)=>{if(!e.has(t))throw TypeError("Cannot "+i)},Ml=(t,e,i)=>(lu(t,e,"read from private field"),i?i.call(t):e.get(t)),du=(t,e,i)=>{if(e.has(t))throw TypeError("Cannot add the same private member more than once");e instanceof WeakSet?e.add(t):e.set(t,i)},cu=1,uu=t=>t.mediaMuted?0:t.mediaVolume,hu=t=>`${Math.round(t*100)}%`,Po=class extends Le{constructor(){super(...arguments),du(this,gr,()=>{let e=this.range.value,i=new n.CustomEvent(h.MEDIA_VOLUME_REQUEST,{composed:!0,bubbles:!0,detail:e});this.dispatchEvent(i)})}static get observedAttributes(){return[...super.observedAttributes,o.MEDIA_VOLUME,o.MEDIA_MUTED,o.MEDIA_VOLUME_UNAVAILABLE]}connectedCallback(){super.connectedCallback(),this.range.setAttribute("aria-label",m("volume")),this.range.addEventListener("input",Ml(this,gr))}disconnectedCallback(){this.range.removeEventListener("input",Ml(this,gr)),super.disconnectedCallback()}attributeChangedCallback(e,i,a){super.attributeChangedCallback(e,i,a),(e===o.MEDIA_VOLUME||e===o.MEDIA_MUTED)&&(this.range.valueAsNumber=uu(this),this.range.setAttribute("aria-valuetext",hu(this.range.valueAsNumber)),this.updateBar())}get mediaVolume(){return x(this,o.MEDIA_VOLUME,cu)}set mediaVolume(e){H(this,o.MEDIA_VOLUME,e)}get mediaMuted(){return _(this,o.MEDIA_MUTED)}set mediaMuted(e){g(this,o.MEDIA_MUTED,e)}get mediaVolumeUnavailable(){return D(this,o.MEDIA_VOLUME_UNAVAILABLE)}set mediaVolumeUnavailable(e){R(this,o.MEDIA_VOLUME_UNAVAILABLE,e)}};gr=new WeakMap;n.customElements.get("media-volume-range")||n.customElements.define("media-volume-range",Po)});function mu(t){return`
      <style>
        :host {
          min-width: 4ch;
          padding: var(--media-button-padding, var(--media-control-padding, 10px 5px));
          width: 100%;
          display: grid;
          grid-template-columns: 1fr auto;
          gap: 1rem;
          font-weight: var(--media-button-font-weight, normal);
        }

        #checked-indicator {
          display: none;
        }

        :host([${o.MEDIA_LOOP}]) #checked-indicator {
          display: block;
        }
      </style>
      
      <span id="icon">
     </span>

      <div id="checked-indicator">
        <svg aria-hidden="true" viewBox="0 1 24 24" part="checked-indicator indicator">
          <path d="m10 15.17 9.193-9.191 1.414 1.414-10.606 10.606-6.364-6.364 1.414-1.414 4.95 4.95Z"/>
        </svg>
      </div>
    `}function pu(){return m("Loop")}var Vi,kl=b(()=>{oe();L();C();U();W();Vi=class extends P{constructor(){super(...arguments),this.container=null}static get observedAttributes(){return[...super.observedAttributes,o.MEDIA_LOOP]}connectedCallback(){var e;super.connectedCallback(),this.container=((e=this.shadowRoot)==null?void 0:e.querySelector("#icon"))||null,this.container&&(this.container.textContent=m("Loop"))}attributeChangedCallback(e,i,a){super.attributeChangedCallback(e,i,a),e===o.MEDIA_LOOP&&this.container&&this.setAttribute("aria-checked",this.mediaLoop?"true":"false")}get mediaLoop(){return _(this,o.MEDIA_LOOP)}set mediaLoop(e){g(this,o.MEDIA_LOOP,e)}handleClick(){let e=!this.mediaLoop,i=new n.CustomEvent(h.MEDIA_LOOP_REQUEST,{composed:!0,bubbles:!0,detail:e});this.dispatchEvent(i)}};Vi.getSlotTemplateHTML=mu;Vi.getTooltipContentHTML=pu;n.customElements.get("media-loop-button")||n.customElements.define("media-loop-button",Vi)});var Ll=b(()=>{C();gt();W();dn();mn();fn();gn();oe();Sa();xa();Dn();xn();Bn();Wn();Gn();aa();Yn();Xn();el();al();rl();sl();nl();fo();ja();go();hl();ml();fl();Sl();Yr();yl();Cr();Nt();kl()});var Eu=Nl(()=>{Ll()});Eu();})();
